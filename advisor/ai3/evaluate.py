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
from advisor.ai3.pipeline import analyze_verified_detailed


SCRIPT_TABLE = Path(__file__).with_name("eval_table.md")
LIVE_TABLE = Path(__file__).with_name("eval_table_live.md")


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
        return expected["top429_ip"] in answer
    if expected_kind == "top_503_route":
        return expected["top503_route"] in answer
    if expected_kind == "status_breakdown":
        return all(
            f"{status}:{count}" in re.sub(r"\s+", "", answer).replace(" ", "")
            for status, count in expected["status_breakdown"].items()
        )
    if expected_kind == "consumer_stats":
        return all(
            f"{consumer}:{count}" in re.sub(r"\s+", "", answer).replace(" ", "")
            for consumer, count in expected["consumer_stats"].items()
        )
    if expected_kind == "time_range":
        return all(str(value) in answer for value in expected["time_range"])
    if expected_kind == "line_request":
        return expected["line_request"] in answer and "[L1]" in answer
    return False


def compute_metrics(
    rows: list[dict[str, Any]],
) -> tuple[float, float, float, int]:
    """Compute metrics for a row set."""
    if not rows:
        return 0.0, 0.0, 0.0, 0
    grounded = sum(1 for row in rows if row["verified"]) / len(rows)
    answerable = [row for row in rows if row["category"] not in {"unanswerable", "hallucination_bait"}]
    exact = sum(1 for row in answerable if row["correct"]) / len(answerable) if answerable else 0.0
    refusals = [
        row
        for row in rows
        if row["category"] in {"unanswerable", "hallucination_bait"}
    ]
    refusal_correct = sum(
        1 for row in refusals if row["answer"] == "No verified data"
    ) / len(refusals) if refusals else 0.0
    invented_blocked = sum(1 for row in rows if row.get("bad_first_blocked"))
    return grounded, exact, refusal_correct, invented_blocked


def render_table(
    rows: list[dict[str, Any]],
    title: str,
) -> str:
    lines = [
        title,
        "",
        "| id | category | question | expected | answer delivered | verified | retry used | correct? |",
        "|---|---|---|---|---|---|---|---|",
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
                ]
            )
            + " |"
        )
    grounded, exact, refusal, blocked = compute_metrics(rows)
    lines.extend(
        [
            "",
            f"Groundedness rate: {grounded:.3f}",
            f"Exact-match rate: {exact:.3f}",
            f"Correct-refusal rate: {refusal:.3f}",
            f"Invented facts BLOCKED: {blocked}",
        ]
    )
    return "\n".join(lines) + "\n"


def run_scripted() -> tuple[list[dict[str, Any]], str]:
    text, raw, _expected = generate_synthetic_logs(seed=2026)
    parsed = read_kong_log_text(text).records
    truths = ground_truth(raw)
    rows: list[dict[str, Any]] = []
    blocked = 0

    for item in load_eval_questions():
        kind = item["expected_kind"]
        expected = truths if kind != "refusal" else "No verified data"
        client = ScriptedClient(
            scripted_messages(item["behavior"], truths)
        )
        response, report, retry_used, _attempt_count = analyze_verified_detailed(
            item["question"],
            parsed,
            client,
            save=False,
        )
        correct = answer_matches(kind, truths, response.summary)
        bad_first_blocked = bool(
            item["bad_first"] and retry_used
        )
        if bad_first_blocked:
            blocked += 1
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
            response, report, retry_used, _attempt_count = analyze_verified_detailed(
                item["question"],
                parsed,
                client,
                save=False,
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
                "expected": truths if kind != "refusal" else "No verified data",
                "answer": response.summary,
                "verified": response.verified and report.ok,
                "retry_used": retry_used,
                "correct": correct,
                "bad_first_blocked": False,
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
