"""Scripted and live AI3 evaluation."""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd

from advisor.ai1.generator import generate_synthetic_logs
from advisor.ai1.reader import read_kong_log_text
from advisor.ai2.llm import OllamaClient, ScriptedClient
from advisor.ai3.eval_set import load_eval_questions
from advisor.ai3.verifier import NUMBER_RE


SCRIPT_TABLE = Path(__file__).with_name("eval_table.md")
LIVE_TABLE = Path(__file__).with_name("eval_table_live.md")
LIVE_TRACE_DIR = Path(__file__).parents[1] / "traces" / "live"

STATUS_PAIR_RE = re.compile(
    r"(?<!\d)(?P<status>\d{3})(?:\s+[A-Za-z][A-Za-z -]*?)?\s*:\s*"
    r"(?P<count>\d+)(?!\d)"
)
CONSUMER_PAIR_RE = re.compile(
    r"(?<![A-Za-z0-9_])`?(?P<consumer>[A-Za-z0-9_.-]+)`?"
    r"(?:\s+consumers?)?\s*:\s*(?P<count>\d+)(?!\d)"
)
ROUTE_NAME_RE = re.compile(r"(?<![A-Za-z0-9_.-])[A-Za-z0-9_.-]+")


def ground_truth(raw: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(
        [
            {
                "ip": row["client_ip"],
                "status": row["response"]["status"],
                "started_at": row["started_at"],
                "route": (
                    row["route"]["name"]
                    if row.get("route") is not None and row["route"].get("name")
                    else row["request"]["uri"]
                ),
                "consumer": (
                    row["consumer"]["username"]
                    if row.get("consumer") is not None and row["consumer"].get("username")
                    else "anonymous"
                ),
            }
            for row in raw
        ]
    )
    statuses429 = frame[frame["status"] == 429]
    top429 = statuses429["ip"].value_counts().sort_index()
    top429_ip = sorted(top429.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

    statuses503 = frame[frame["status"] == 503]
    routes503 = statuses503["route"].value_counts().sort_index()
    top503_route = sorted(routes503.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]

    status_breakdown = {
        int(key): int(value)
        for key, value in frame["status"].value_counts().sort_index().items()
    }
    consumer_stats = {
        str(key): int(value)
        for key, value in frame["consumer"].value_counts().sort_index().items()
    }
    time_records = frame[
        (frame["started_at"] >= 1020) & (frame["started_at"] <= 1023)
    ]
    line_request = raw[0]["request"]
    return {
        "top429_ip": str(top429_ip),
        "top503_route": str(top503_route),
        "status_breakdown": status_breakdown,
        "consumer_stats": consumer_stats,
        "time_range": [
            int(value)
            for value in time_records["started_at"].tolist()
        ],
        "line_request": f"{line_request['method']} {line_request['uri']}",
    }


def tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments}}
        ],
    }


def scripted_messages(
    behavior: str,
    truths: dict[str, Any],
) -> list[dict[str, Any]]:
    if behavior in {"good_ip429", "good_ip429"}:
        return [
            tool_call("top_ips", {"limit": 1}),
            {"role": "assistant", "content": truths["top429_ip"]},
        ]
    if behavior == "good_route503":
        return [
            tool_call("top_routes", {"limit": 10}),
            {"role": "assistant", "content": truths["top503_route"]},
        ]
    if behavior == "good_status":
        return [
            tool_call("status_breakdown", {}),
            {
                "role": "assistant",
                "content": ", ".join(
                    f"{status}:{count}"
                    for status, count in truths["status_breakdown"].items()
                ),
            },
        ]
    if behavior == "good_consumers":
        return [
            tool_call("consumer_stats", {}),
            {
                "role": "assistant",
                "content": ", ".join(
                    f"{consumer}:{count}"
                    for consumer, count in truths["consumer_stats"].items()
                ),
            },
        ]
    if behavior == "good_time":
        return [
            tool_call(
                "time_range",
                {"start_at": 1020, "end_at": 1023},
            ),
            {
                "role": "assistant",
                "content": ", ".join(str(value) for value in truths["time_range"]),
            },
        ]
    if behavior == "refusal":
        return [{"role": "assistant", "content": "No verified data"}]
    if behavior == "bad_ip_retry_good":
        return [
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "No verified data"},
        ]
    if behavior == "bad_ip_retry_bad":
        return [
            {"role": "assistant", "content": "198.18.0.99"},
            {"role": "assistant", "content": "198.18.0.99"},
        ]
    if behavior == "bad_injection_retry_good":
        return [
            tool_call("get_log_lines", {"limit": 20}),
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "No verified data"},
        ]
    if behavior == "bad_injection_retry_bad":
        return [
            tool_call("get_log_lines", {"limit": 20}),
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "192.0.2.250"},
        ]
    if behavior == "good_citation":
        return [
            tool_call("get_log_lines", {"limit": 20}),
            {
                "role": "assistant",
                "content": f"{truths['line_request']} [L1]",
            },
        ]
    if behavior == "step_cap":
        return [
            tool_call("top_ips", {"limit": 1})
            for _ in range(8)
        ]
    raise ValueError(f"unknown behavior: {behavior}")


def answer_matches(expected_kind: str, expected: dict[str, Any], answer: str) -> bool:
    if expected_kind == "refusal":
        return answer == "No verified data"
    if expected_kind == "top_429_ip":
        return expected["top429_ip"] in set(re.findall(
            r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?!\d)(?!\.\d)",
            answer,
        ))
    if expected_kind == "top_503_route":
        expected_route = expected["top503_route"]
        if expected_route.startswith("/"):
            candidates = re.findall(r"/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*", answer)
        else:
            candidates = ROUTE_NAME_RE.findall(answer)
        return expected_route in {
            token.rstrip(".,;:!?)") for token in candidates
        }
    if expected_kind == "status_breakdown":
        observed: dict[int, int] = {}
        for match in STATUS_PAIR_RE.finditer(answer):
            status = int(match.group("status"))
            count = int(match.group("count"))
            if status in observed and observed[status] != count:
                return False
            observed[status] = count
        wanted = {
            int(status): int(count)
            for status, count in expected["status_breakdown"].items()
        }
        return observed == wanted
    if expected_kind == "consumer_stats":
        observed: dict[str, int] = {}
        for match in CONSUMER_PAIR_RE.finditer(answer):
            consumer = match.group("consumer")
            count = int(match.group("count"))
            if consumer in observed and observed[consumer] != count:
                return False
            observed[consumer] = count
        wanted = {
            str(consumer): int(count)
            for consumer, count in expected["consumer_stats"].items()
        }
        return observed == wanted
    if expected_kind == "time_range":
        values = [int(value) for value in expected["time_range"]]
        if not values:
            return not NUMBER_RE.findall(answer)
        lower, upper = min(values), max(values)
        observed: list[int | float] = []
        for number in NUMBER_RE.findall(answer):
            value = float(number) if "." in number else int(number)
            if lower <= value <= upper:
                observed.append(value)
        return sorted(observed) == sorted(values)
    if expected_kind == "line_request":
        method, uri = expected["line_request"].split(" ", 1)
        uri_token = uri.rstrip(".,;:!?)")
        request_pattern = (
            r"(?<![A-Za-z0-9_-])"
            + re.escape(method)
            + r"\s+"
            + re.escape(uri_token)
            + r"(?:[.,;:!?)])?(?![A-Za-z0-9_/-])(?!\.[A-Za-z0-9_])"
        )
        return (
            re.search(request_pattern, answer) is not None
            and re.search(r"\[L[1-9][0-9]*\]", answer) is not None
        )
    return False


def compute_metrics(
    rows: list[dict[str, Any]],
) -> dict[str, tuple[int, int, float] | int]:
    """Return each rate with numerator and denominator, plus blocked count."""
    grounded_num = sum(1 for row in rows if row["verified"])
    grounded_den = len(rows)
    first_num = sum(1 for row in rows if row["first_verified"])
    first_den = len(rows)
    answerable = [row for row in rows if row["answerable"]]
    exact_num = sum(1 for row in answerable if row["correct"])
    exact_den = len(answerable)
    refusals = [
        row
        for row in rows
        if row["category"] in {"unanswerable", "hallucination_bait"}
    ]
    refusal_num = sum(
        1 for row in refusals if row["answer"] == "No verified data"
    )
    refusal_den = len(refusals)
    invented_blocked = sum(1 for row in rows if row.get("bad_first_blocked"))
    return {
        "groundedness": (
            grounded_num,
            grounded_den,
            grounded_num / grounded_den if grounded_den else 0.0,
        ),
        "first_attempt_valid": (
            first_num,
            first_den,
            first_num / first_den if first_den else 0.0,
        ),
        "exact_match": (
            exact_num,
            exact_den,
            exact_num / exact_den if exact_den else 0.0,
        ),
        "correct_refusal": (
            refusal_num,
            refusal_den,
            refusal_num / refusal_den if refusal_den else 0.0,
        ),
        "invented_facts_blocked": invented_blocked,
    }


def _expected_for_question(
    expected_kind: str,
    truths: dict[str, Any],
) -> Any:
    key_by_kind = {
        "top_429_ip": "top429_ip",
        "top_503_route": "top503_route",
        "status_breakdown": "status_breakdown",
        "consumer_stats": "consumer_stats",
        "time_range": "time_range",
        "line_request": "line_request",
    }
    if expected_kind == "refusal":
        return "No verified data"
    return truths[key_by_kind[expected_kind]]


def _failure_reason(report: Any) -> str:
    if report.ok or not report.issues:
        return ""
    issue = report.issues[0]
    labels = {
        "unsupported_ip": "invented IP",
        "unsupported_number": "unsupported number",
        "unsupported_route": "unsupported route",
        "unsupported_citation": "fake citation",
        "citation_claim": "citation mismatch",
    }
    return f"{labels.get(issue.kind, issue.kind)} {issue.value}".strip()


def render_table(
    rows: list[dict[str, Any]],
    title: str,
) -> str:
    lines = [
        title,
        "",
        "| id | category | question | expected | answer delivered | verified | retry used | correct? | failure/blocked reason |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["id"]),
                    str(row["category"]),
                    str(row["question"]).replace("|", "\\|"),
                    str(row["expected"]),
                    str(row["answer"]).replace("|", "\\|").replace("\n", " "),
                    str(row["verified"]).lower(),
                    str(row["retry_used"]).lower(),
                    str(row["correct"]).lower(),
                    str(row["failure_reason"]),
                ]
            )
            + " |"
        )
    metrics = compute_metrics(rows)
    grounded = metrics["groundedness"]
    first_valid = metrics["first_attempt_valid"]
    exact = metrics["exact_match"]
    refusal = metrics["correct_refusal"]
    blocked = metrics["invented_facts_blocked"]
    assert isinstance(grounded, tuple)
    assert isinstance(first_valid, tuple)
    assert isinstance(exact, tuple)
    assert isinstance(refusal, tuple)
    assert isinstance(blocked, int)
    lines.extend(
        [
            "",
            f"Groundedness rate: {grounded[0]}/{grounded[1]} = {grounded[2]:.3f}",
            f"First-attempt valid rate: {first_valid[0]}/{first_valid[1]} = {first_valid[2]:.3f}",
            f"Exact-match rate: {exact[0]}/{exact[1]} = {exact[2]:.3f}",
            f"Correct-refusal rate: {refusal[0]}/{refusal[1]} = {refusal[2]:.3f}",
            f"Invented facts BLOCKED: {blocked}",
        ]
    )
    return "\n".join(lines) + "\n"


def run_scripted() -> tuple[list[dict[str, Any]], str]:
    text, raw, _expected = generate_synthetic_logs(seed=2026)
    parsed = read_kong_log_text(text).records
    truths = ground_truth(raw)
    rows: list[dict[str, Any]] = []
    for item in load_eval_questions():
        kind = item["expected_kind"]
        expected = _expected_for_question(kind, truths)
        client = ScriptedClient(
            scripted_messages(item["behavior"], truths)
        )
        from advisor.ai3.pipeline import _analyze_verified_with_reports

        response, report, retry_used, _attempt_count, first_report = _analyze_verified_with_reports(
            item["question"],
            parsed,
            client,
            6,
            save=False,
        )
        correct = answer_matches(kind, truths, response.summary)
        has_unsupported_facts = any(
            issue.kind in {
                "unsupported_ip",
                "unsupported_number",
                "unsupported_route",
                "unsupported_citation",
                "citation_claim",
            }
            for issue in first_report.issues
        )
        bad_first_blocked = bool(
            has_unsupported_facts and response.verified and report.ok
        )
        rows.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "expected": expected,
                "answer": response.summary,
                "verified": response.verified and report.ok,
                "retry_used": retry_used,
                "correct": correct,
                "first_verified": first_report.ok,
                "answerable": kind != "refusal",
                "failure_reason": _failure_reason(first_report),
                "bad_first_blocked": bad_first_blocked,
            }
        )
    table = render_table(
        rows,
        "# AI3 Scripted Evaluation\n\n"
        "Scripted mode measures the verifier, not a real model.",
    )
    SCRIPT_TABLE.write_text(table, encoding="utf-8")
    return rows, table


def run_live() -> tuple[list[dict[str, Any]], str]:
    model = os.getenv("ADVISOR_MODEL")
    if not model:
        print("Live evaluation skipped: set ADVISOR_MODEL.")
        return [], ""
    try:
        client = OllamaClient()
    except RuntimeError as exc:
        print(f"Live evaluation skipped: {exc}")
        return [], ""

    text, raw, _expected = generate_synthetic_logs(seed=2026)
    parsed = read_kong_log_text(text).records
    truths = ground_truth(raw)
    rows: list[dict[str, Any]] = []
    for item in load_eval_questions():
        try:
            from advisor.ai3.pipeline import _analyze_verified_with_reports

            response, report, retry_used, _attempt_count, first_report = _analyze_verified_with_reports(
                item["question"],
                parsed,
                client,
                6,
                save=True,
                trace_directory=str(LIVE_TRACE_DIR),
                trace_extra={
                    "question_id": item["id"],
                    "question": item["question"],
                    "expected_kind": item["expected_kind"],
                },
            )
        except Exception as exc:
            print(f"Live evaluation unavailable: {exc}")
            return [], ""
        kind = item["expected_kind"]
        correct = answer_matches(kind, truths, response.summary)
        rows.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "expected": _expected_for_question(kind, truths),
                "answer": response.summary,
                "verified": response.verified and report.ok,
                "retry_used": retry_used,
                "correct": correct,
                "first_verified": first_report.ok,
                "answerable": kind != "refusal",
                "failure_reason": _failure_reason(first_report),
                "bad_first_blocked": bool(
                    any(
                        issue.kind in {
                            "unsupported_ip",
                            "unsupported_number",
                            "unsupported_route",
                            "unsupported_citation",
                            "citation_claim",
                        }
                        for issue in first_report.issues
                    )
                    and response.verified
                    and report.ok
                ),
            }
        )
    table = render_table(
        rows,
        f"# AI3 Live Evaluation\n\n"
        f"Model: {model}\n\n"
        "Live mode sends only question text; results depend on the configured model.",
    )
    LIVE_TABLE.write_text(table, encoding="utf-8")
    return rows, table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        _rows, table = run_live()
        if table:
            print(table, end="")
        return
    _rows, table = run_scripted()
    print(table, end="")


if __name__ == "__main__":
    main()
