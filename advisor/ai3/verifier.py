"""Pure-Python verification of AI2 answers against tool-trace evidence."""

import ipaddress
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from advisor.ai2.agent import AnalyzeResponse


IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
CITATION_RE = re.compile(r"\[L([1-9][0-9]*)\]")
PATH_RE = re.compile(r"/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*")
NUMBER_RE = re.compile(r"(?<![\w.])[-+]?(?:\d+\.\d+|\d+(?![\d.]))(?![\w.])")


class ExtractedFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ips: list[str]
    routes: list[str]
    numbers: list[int | float]
    citations: list[str]


class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    value: str
    reason: str


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    facts: ExtractedFacts
    issues: list[VerificationIssue]


def _values(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield key
            yield from _values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _values(nested)
    else:
        yield value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _canonical_number(value: int | float) -> int | float:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build_evidence(
    response: AnalyzeResponse,
) -> tuple[set[str], set[str], set[int | float], set[str], dict[str, dict[str, Any]]]:
    """Build evidence solely from tool_trace result summaries and arguments.

    Numeric values in tool arguments are allowed evidence. They do not come
    from the raw log file or the question.
    """
    ips: set[str] = set()
    routes: set[str] = set()
    numbers: set[int | float] = set()
    citations: set[str] = set()
    line_records: dict[str, dict[str, Any]] = {}

    for trace in response.tool_trace:
        arguments = trace.get("arguments")
        if isinstance(arguments, Mapping):
            for value in _values(arguments):
                if _is_number(value):
                    numbers.add(_canonical_number(value))

        tool_name = trace.get("tool")
        summary = trace.get("result_summary", "")
        if not isinstance(summary, str) or not summary:
            continue
        try:
            result = json.loads(summary)
        except json.JSONDecodeError:
            continue

        for value in _values(result):
            if isinstance(value, str):
                if re.fullmatch(r"\d+(?:\.\d+)?", value):
                    if "." in value:
                        numbers.add(_canonical_number(float(value)))
                    else:
                        numbers.add(_canonical_number(int(value)))
                for match in IP_RE.findall(value):
                    try:
                        ips.add(str(ipaddress.IPv4Address(match)))
                    except ipaddress.AddressValueError:
                        pass
                if value.startswith("/") and value not in {"/"}:
                    routes.add(value)
            if _is_number(value):
                numbers.add(_canonical_number(value))

        if isinstance(result, list):
            for row in result:
                if not isinstance(row, Mapping):
                    continue
                ip = row.get("client_ip")
                if isinstance(ip, str):
                    ips.add(ip)
                route = row.get("route")
                if isinstance(route, str):
                    routes.add(route)

                record = row.get("record")
                line_id = row.get("line_id")
                if tool_name == "get_log_lines" and isinstance(line_id, str):
                    citations.add(line_id)
                    if isinstance(record, Mapping):
                        line_records[line_id] = dict(record)

        if tool_name == "get_log_lines":
            if isinstance(result, list):
                for row in result:
                    if not isinstance(row, Mapping):
                        continue
                    line_id = row.get("line_id")
                    record = row.get("record")
                    if isinstance(line_id, str) and isinstance(record, Mapping):
                        citations.add(line_id)
                        line_records[line_id] = dict(record)

    return ips, routes, numbers, citations, line_records


def extract_facts(answer: str, evidence_routes: set[str]) -> ExtractedFacts:
    ips = sorted(set(IP_RE.findall(answer)))

    routes = set(PATH_RE.findall(answer))
    for route in evidence_routes:
        if route.startswith("/"):
            continue
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(route)}(?![A-Za-z0-9_-])", answer):
            routes.add(route)

    masked = IP_RE.sub(" ", answer)
    masked = CITATION_RE.sub(" ", masked)
    for route in sorted(routes, key=len, reverse=True):
        masked = masked.replace(route, " ")

    numbers: set[int | float] = set()
    for match in NUMBER_RE.findall(masked):
        try:
            text = match
            value: int | float
            if "." in text:
                value = float(text)
            else:
                value = int(text)
            numbers.add(_canonical_number(value))
        except ValueError:
            continue

    citations = sorted(set(f"[L{number}]" for number in CITATION_RE.findall(answer)))
    return ExtractedFacts(
        ips=ips,
        routes=sorted(routes),
        numbers=sorted(numbers),
        citations=citations,
    )


def _line_contains(line_record: Mapping[str, Any], value: str) -> bool:
    if value.startswith("/"):
        request = line_record.get("request")
        route = line_record.get("route")
        if isinstance(request, Mapping) and request.get("uri") == value:
            return True
        if isinstance(route, Mapping) and route.get("name") == value:
            return True
        return False
    return any(
        isinstance(candidate, str) and candidate == value
        for candidate in _values(line_record)
    )


def verify_answer(answer: str, response: AnalyzeResponse) -> VerificationReport:
    """Verify a delivered answer against evidence from this AI2 run."""
    if answer == "No verified data":
        return VerificationReport(
            ok=True,
            facts=ExtractedFacts(ips=[], routes=[], numbers=[], citations=[]),
            issues=[],
        )
    if not answer.strip():
        facts = ExtractedFacts(ips=[], routes=[], numbers=[], citations=[])
        return VerificationReport(
            ok=False,
            facts=facts,
            issues=[
                VerificationIssue(
                    kind="empty_answer",
                    value="",
                    reason="Empty answers cannot be verified",
                )
            ],
        )

    ips, routes, numbers, returned_citations, line_records = build_evidence(response)
    facts = extract_facts(answer, routes)
    issues: list[VerificationIssue] = []

    for ip in facts.ips:
        if ip not in ips:
            issues.append(
                VerificationIssue(
                    kind="unsupported_ip",
                    value=ip,
                    reason="IP is absent from tool trace evidence",
                )
            )
    for route in facts.routes:
        if route not in routes:
            issues.append(
                VerificationIssue(
                    kind="unsupported_route",
                    value=route,
                    reason="Route is absent from tool trace evidence",
                )
            )
    for number in facts.numbers:
        if number not in numbers:
            issues.append(
                VerificationIssue(
                    kind="unsupported_number",
                    value=str(number),
                    reason="Number is absent from tool arguments or tool trace evidence",
                )
            )
    for citation in facts.citations:
        line_id = citation[1:-1]
        if line_id not in returned_citations:
            issues.append(
                VerificationIssue(
                    kind="unsupported_citation",
                    value=citation,
                    reason="Citation ID was not returned by get_log_lines in this run",
                )
            )

    for sentence in re.split(r"(?<=[.!?])\s+", answer):
        cited = CITATION_RE.findall(sentence)
        if not cited:
            continue
        ips_in_sentence = IP_RE.findall(sentence)
        routes_in_sentence = set(PATH_RE.findall(sentence))
        for route in routes:
            if route.startswith("/") or not route:
                continue
            if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(route)}(?![A-Za-z0-9_-])", sentence):
                routes_in_sentence.add(route)
        for line_number in cited:
            line_id = f"L{line_number}"
            record = line_records.get(line_id)
            if record is None:
                continue
            for ip in ips_in_sentence:
                if not _line_contains(record, ip):
                    issues.append(
                        VerificationIssue(
                            kind="citation_claim",
                            value=f"{line_id}:{ip}",
                            reason="Cited record does not contain the IP mentioned in the sentence",
                        )
                    )
            for route in routes_in_sentence:
                if not _line_contains(record, route):
                    issues.append(
                        VerificationIssue(
                            kind="citation_claim",
                            value=f"{line_id}:{route}",
                            reason="Cited record does not contain the route mentioned in the sentence",
                        )
                    )

    return VerificationReport(
        ok=not issues,
        facts=facts,
        issues=issues,
    )
