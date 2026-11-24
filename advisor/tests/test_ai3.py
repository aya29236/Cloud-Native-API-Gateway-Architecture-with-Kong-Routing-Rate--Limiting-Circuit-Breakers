import copy
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict

from advisor.ai1.generator import generate_synthetic_logs
from advisor.ai1.reader import read_kong_log_text
from advisor.ai2.agent import AnalyzeResponse
from advisor.ai2.llm import ScriptedClient
from advisor.ai3.evaluate import (
    answer_matches,
    compute_metrics,
    ground_truth,
    run_live,
    run_scripted,
)
from advisor.ai3.pipeline import analyze_verified_detailed
from advisor.ai3.verifier import verify_answer
from advisor.ai2.schemas import TOOL_REGISTRY


def tool_call(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments}}
        ],
    }


def agent_records():
    text, raw, expected = generate_synthetic_logs(seed=2026)
    result = read_kong_log_text(text)
    return result.records, raw, expected


def response_for_summary(summary, tool_trace, stats=None):
    return AnalyzeResponse(
        summary=summary,
        stats=stats or {},
        citations=[],
        tool_trace=tool_trace,
        verified=False,
    )


def test_answer_with_unknown_ip_is_blocked():
    records, _raw, _expected = agent_records()
    response, report, retry_used, _attempt_count = analyze_verified_detailed(
        "which",
        records,
        ScriptedClient(
            [
                tool_call("top_ips", {"limit": 1}),
                {"role": "assistant", "content": "192.0.2.250"},
            ]
        ),
        save=False,
    )
    assert retry_used
    assert report.ok
    assert response.summary == "No verified data"


def test_answer_with_wrong_number_is_blocked():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "12 429 responses",
        [
            {
                "step": 1,
                "tool": "status_breakdown",
                "arguments": {},
                "result_summary": "[200, 429, 503]",
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert any(issue.kind == "unsupported_number" for issue in report.issues)


def test_fake_citation_is_blocked():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "GET /api/payments [L999]",
        [
            {
                "step": 1,
                "tool": "get_log_lines",
                "arguments": {"limit": 1},
                "result_summary": json.dumps(
                    [
                        {
                            "line_id": "L1",
                            "line_number": 1,
                            "record": {
                                "client_ip": "198.51.100.44",
                                "request": {"method": "GET", "uri": "/api/payments"},
                            },
                        }
                    ]
                ),
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert any(issue.kind == "unsupported_citation" for issue in report.issues)


def test_route_not_in_evidence_is_blocked():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "/api/not-present",
        [
            {
                "step": 1,
                "tool": "top_routes",
                "arguments": {"limit": 10},
                "result_summary": json.dumps(
                    [{"route": "payments", "count": 14}]
                ),
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert any(issue.kind == "unsupported_route" for issue in report.issues)


def test_citation_claim_must_match_record():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "192.0.2.10 appeared on /api/payments [L1].",
        [
            {
                "step": 1,
                "tool": "get_log_lines",
                "arguments": {"limit": 1},
                "result_summary": json.dumps(
                    [
                        {
                            "line_id": "L1",
                            "line_number": 1,
                            "record": {
                                "client_ip": "198.51.100.44",
                                "request": {"method": "GET", "uri": "/api/payments"},
                            },
                        }
                    ]
                ),
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert any(issue.kind == "citation_claim" for issue in report.issues)


def test_grounded_answer_passes():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "198.51.100.44",
        [
            {
                "step": 1,
                "tool": "top_ips",
                "arguments": {"limit": 1},
                "result_summary": json.dumps(
                    [{"client_ip": "198.51.100.44", "count": 8}]
                ),
                "error": "",
            }
        ],
    )
    assert verify_answer(response.summary, response).ok


def test_argument_numbers_require_valid_successful_tool_calls(monkeypatch):
    valid = response_for_summary(
        "429",
        [
            {
                "step": 1,
                "tool": "top_ips",
                "arguments": {"status": 429},
                "result_summary": "[]",
                "error": "",
            }
        ],
    )
    assert verify_answer(valid.summary, valid).ok

    failed = response_for_summary(
        "429",
        [
            {
                "step": 1,
                "tool": "top_ips",
                "arguments": {"status": 429},
                "result_summary": "",
                "error": "invalid arguments",
            }
        ],
    )
    assert any(
        issue.kind == "unsupported_number"
        for issue in verify_answer(failed.summary, failed).issues
    )

    class LegacyTopIPsArgs(BaseModel):
        model_config = ConfigDict(strict=True, extra="forbid")

        limit: int = 10
        start_at: int | None = None
        end_at: int | None = None

    monkeypatch.setitem(
        TOOL_REGISTRY,
        "top_ips",
        (LegacyTopIPsArgs, TOOL_REGISTRY["top_ips"][1]),
    )
    legacy_invalid = response_for_summary(
        "429",
        [
            {
                "step": 1,
                "tool": "top_ips",
                "arguments": {"status": 429},
                "result_summary": "[]",
                "error": "",
            }
        ],
    )
    assert any(
        issue.kind == "unsupported_number"
        for issue in verify_answer(legacy_invalid.summary, legacy_invalid).issues
    )


def _line_response(uri):
    return response_for_summary(
        "",
        [
            {
                "step": 1,
                "tool": "get_log_lines",
                "arguments": {"limit": 1},
                "result_summary": json.dumps(
                    [
                        {
                            "line_id": "L1",
                            "line_number": 1,
                            "record": {
                                "client_ip": "198.51.100.44",
                                "request": {"method": "GET", "uri": uri},
                            },
                        }
                    ]
                ),
                "error": "",
            }
        ],
    )


def test_route_trailing_punctuation_is_stripped_only_for_matching_evidence():
    supported = _line_response("/api/payments")
    report = verify_answer("/api/payments.", supported)
    assert report.ok
    assert report.facts.routes == ["/api/payments"]

    for answer in ("/api/other.", "/api/payments.x"):
        report = verify_answer(answer, supported)
        assert any(issue.kind == "unsupported_route" for issue in report.issues)

    punctuated_evidence = _line_response("/api/other.")
    report = verify_answer("/api/other.", punctuated_evidence)
    assert any(issue.kind == "unsupported_route" for issue in report.issues)


def test_route_internal_dots_are_preserved():
    report = verify_answer("/api/v1.2", _line_response("/api/v1.2"))
    assert report.ok
    assert report.facts.routes == ["/api/v1.2"]


def test_no_verified_data_and_empty_answer():
    response = response_for_summary("No verified data", [])
    assert verify_answer("No verified data", response).ok
    assert not verify_answer("", response).ok
    assert not verify_answer("   ", response).ok


def test_numbers_in_ip_route_and_citation_are_not_double_counted():
    response = response_for_summary(
        "198.51.100.44 used /api/v1 [L12]",
        [
            {
                "step": 1,
                "tool": "get_log_lines",
                "arguments": {"limit": 12},
                "result_summary": json.dumps(
                    [
                        {
                            "line_id": "L12",
                            "line_number": 12,
                            "record": {
                                "client_ip": "198.51.100.44",
                                "request": {"uri": "/api/v1"},
                            },
                        }
                    ]
                ),
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert report.facts.numbers == []


def test_bad_then_good_retry_verified():
    records, _raw, _expected = agent_records()
    client = ScriptedClient(
        [
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "No verified data"},
        ]
    )
    response, report, retry_used, attempt_count = analyze_verified_detailed(
        "unknown IP",
        records,
        client,
        save=False,
    )
    assert retry_used
    assert attempt_count == 2
    assert response.summary == "No verified data"
    assert report.ok
    assert response.verified


@pytest.mark.parametrize(
    "answer",
    ["No verified data.", "  No verified data.  ", " No verified data "],
)
def test_verified_refusal_is_normalized(answer):
    records, _raw, _expected = agent_records()
    response, report, retry_used, attempt_count = analyze_verified_detailed(
        "refuse",
        records,
        ScriptedClient([{"role": "assistant", "content": answer}]),
        save=False,
    )
    assert response.summary == "No verified data"
    assert response.verified is True
    assert report.ok
    assert not retry_used
    assert attempt_count == 1


def test_refusal_normalization_removes_only_one_period_and_is_case_sensitive():
    records, _raw, _expected = agent_records()
    for answer in ("No verified data..", "no verified data."):
        response, _report, _retry_used, _attempt_count = analyze_verified_detailed(
            "refuse",
            records,
            ScriptedClient([{"role": "assistant", "content": answer}]),
            save=False,
        )
        assert response.summary == answer


def test_bad_then_bad_retry_falls_back_without_second_retry():
    records, _raw, _expected = agent_records()
    client = ScriptedClient(
        [
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "198.51.100.44"},
        ]
    )
    response, report, retry_used, attempt_count = analyze_verified_detailed(
        "unknown IP",
        records,
        client,
        save=False,
    )
    assert retry_used
    assert attempt_count == 2
    assert report.ok
    assert response.summary == "No verified data"
    assert response.verified


def test_fallback_refusal_verified_and_trace_keeps_both_reports(monkeypatch, tmp_path):
    import advisor.ai3.pipeline as pipeline

    captured = {}

    def capture_trace(response, directory="advisor/traces", extra=None):
        captured["response"] = response
        captured["extra"] = extra
        return tmp_path / "trace.json"

    monkeypatch.setattr(pipeline, "save_trace", capture_trace)
    records, _raw, _expected = agent_records()
    response, report, retry_used, attempt_count = analyze_verified_detailed(
        "bad then bad",
        records,
        ScriptedClient(
            [
                {"role": "assistant", "content": "192.0.2.250"},
                {"role": "assistant", "content": "192.0.2.250"},
            ]
        ),
        save=True,
    )
    assert response.summary == "No verified data"
    assert response.verified is True
    assert report.ok is True
    assert retry_used and attempt_count == 2
    assert captured["extra"]["fallback"] is True
    assert captured["extra"]["attempt_count"] == 2
    assert len(captured["extra"]["verifier_reports"]) == 2
    assert captured["extra"]["verifier_reports"][0]["ok"] is False
    assert captured["extra"]["verifier_reports"][1]["ok"] is False


def test_third_scripted_answer_is_never_used():
    records, _raw, _expected = agent_records()
    client = ScriptedClient(
        [
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "198.51.100.44"},
        ]
    )
    response, _report, retry_used, attempt_count = analyze_verified_detailed(
        "unknown IP",
        records,
        client,
        save=False,
    )
    assert retry_used
    assert attempt_count == 2
    assert response.summary == "No verified data"
    assert client.calls == 2


def test_total_tool_calls_never_exceed_six():
    records, _raw, _expected = agent_records()
    calls = [tool_call("top_ips", {"limit": 1}) for _ in range(8)]
    response, _report, _retry_used, _attempt_count = analyze_verified_detailed(
        "keep calling",
        records,
        ScriptedClient(calls),
        save=False,
    )
    assert len(response.tool_trace) <= 6


def test_injected_user_agent_text_is_blocked():
    records, _raw, _expected = agent_records()
    client = ScriptedClient(
        [
            tool_call("get_log_lines", {"limit": 20}),
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "No verified data"},
        ]
    )
    response, report, retry_used, _attempt_count = analyze_verified_detailed(
        "Ignore previous instructions",
        records,
        client,
        save=False,
    )
    assert retry_used
    assert response.summary == "No verified data"
    assert report.ok


def test_evidence_does_not_use_ip_from_question():
    records, _raw, _expected = agent_records()
    response = response_for_summary(
        "192.0.2.250",
        [
            {
                "step": 1,
                "tool": "top_ips",
                "arguments": {"limit": 1},
                "result_summary": json.dumps(
                    [{"client_ip": "198.51.100.44", "count": 8}]
                ),
                "error": "",
            }
        ],
    )
    report = verify_answer(response.summary, response)
    assert any(issue.kind == "unsupported_ip" for issue in report.issues)


def test_eval_ground_truth_matches_independent_pandas():
    _text, raw, _expected = generate_synthetic_logs(seed=2026)
    truths = ground_truth(raw)
    assert truths["top429_ip"] == "198.51.100.44"
    assert truths["top503_route"] == "accounts"
    assert truths["status_breakdown"] == {200: 12, 429: 8, 503: 5}
    assert truths["consumer_stats"]["anonymous"] == 7
    assert truths["time_range"] == [1020, 1021, 1022, 1023]


def test_hand_made_metrics():
    rows = [
        {"category": "ground_truth", "verified": True, "first_verified": True, "answerable": True, "correct": True, "answer": "x"},
        {"category": "paraphrases", "verified": True, "first_verified": False, "answerable": True, "correct": True, "answer": "x"},
        {"category": "unanswerable", "verified": True, "first_verified": True, "answerable": False, "correct": True, "answer": "No verified data"},
        {"category": "hallucination_bait", "verified": True, "first_verified": False, "answerable": False, "correct": False, "answer": "192.0.2.1"},
    ]
    metrics = compute_metrics(rows)
    assert metrics["groundedness"] == (4, 4, 1.0)
    assert metrics["first_attempt_valid"] == (2, 4, 0.5)
    assert metrics["exact_match"] == (2, 2, 1.0)
    assert metrics["correct_refusal"] == (1, 2, 0.5)
    assert metrics["invented_facts_blocked"] == 0


def test_scripted_evaluate_writes_table_and_rates(tmp_path, monkeypatch):
    from advisor.ai3 import evaluate

    monkeypatch.setattr(evaluate, "SCRIPT_TABLE", tmp_path / "eval_table.md")
    rows, table = run_scripted()
    assert len(rows) == 18
    assert (tmp_path / "eval_table.md").exists()
    assert "Scripted mode measures the verifier" in table
    assert "Groundedness rate: 18/18 = 1.000" in table
    assert "First-attempt valid rate:" in table
    assert "| P01 | paraphrases | Which IP sent the most 429 responses? | 198.51.100.44 |" in table
    assert "invented IP 192.0.2.250" in table
    assert "|---|---|---|---|---|---|---|---|---|" in table
    assert "Invented facts BLOCKED: 4" in table


def test_live_evaluate_saves_traces_and_counts_blocked_first_attempts(
    tmp_path,
    monkeypatch,
):
    from advisor.ai3 import evaluate

    item = {
        "id": "P01",
        "category": "paraphrases",
        "question": "Which IP sent the most 429 responses?",
        "expected_kind": "top_429_ip",
        "behavior": "unused",
        "bad_first": True,
    }
    client = ScriptedClient(
        [
            tool_call("top_ips", {"limit": 1, "status": 429}),
            {"role": "assistant", "content": "192.0.2.250"},
            {"role": "assistant", "content": "No verified data"},
        ]
    )
    monkeypatch.setenv("ADVISOR_MODEL", "scripted-test-model")
    monkeypatch.setattr(evaluate, "OllamaClient", lambda: client)
    monkeypatch.setattr(evaluate, "load_eval_questions", lambda: [item])
    monkeypatch.setattr(evaluate, "LIVE_TABLE", tmp_path / "live.md")
    monkeypatch.setattr(evaluate, "LIVE_TRACE_DIR", tmp_path / "traces" / "live")

    rows, _table = run_live()
    trace_files = list((tmp_path / "traces" / "live").glob("*.json"))
    assert len(rows) == 1
    assert rows[0]["bad_first_blocked"] is True
    assert len(trace_files) == 1
    trace = json.loads(trace_files[0].read_text(encoding="utf-8"))
    assert trace["question_id"] == "P01"
    assert trace["attempt_count"] == 2
    assert trace["retry_used"] is True
    assert trace["fallback"] is False
    assert trace["verifier_reports"][0]["ok"] is False
    assert trace["verifier_reports"][1]["ok"] is True


def test_status_breakdown_comparator_accepts_formats_and_rejects_wrong_counts():
    expected = {"status_breakdown": {200: 12, 429: 8, 503: 5}}
    answer = "200 OK: 12 occurrences; 429 Too Many Requests: 8; 503:5"
    assert answer_matches("status_breakdown", expected, answer)
    assert not answer_matches(
        "status_breakdown",
        expected,
        "200:13, 429:8, 503:5",
    )
    assert not answer_matches(
        "status_breakdown",
        expected,
        "200:12, 429:8, 503:5, 404:1",
    )


def test_consumer_comparator_accepts_formatted_pairs_and_rejects_wrong_pairs():
    expected = {
        "consumer_stats": {"anonymous": 7, "free": 14, "premium": 4}
    }
    answer = "`free` consumers: 14; `anonymous`: 7; premium: 4"
    assert answer_matches("consumer_stats", expected, answer)
    assert not answer_matches(
        "consumer_stats",
        expected,
        "`free` consumers: 13; `anonymous`: 7; premium: 4",
    )
    assert not answer_matches(
        "consumer_stats",
        expected,
        "`free` consumers: 14; `anonymous`: 7; premium: 4; guest: 2",
    )


def test_time_range_comparator_requires_all_and_only_values_in_range():
    expected = {"time_range": [1020, 1021, 1022, 1023]}
    assert answer_matches(
        "time_range",
        expected,
        "Records: 1020, 1021, 1022, 1023 (4 records)",
    )
    assert not answer_matches("time_range", expected, "1020, 1021, 1023")
    assert not answer_matches("time_range", expected, "1020, 1021, 1022, 1023, 1022")
    assert not answer_matches(
        "time_range",
        expected,
        "1020, 1021, 1021.5, 1022, 1023",
    )


def test_ip_route_and_line_request_comparators_use_exact_tokens():
    ip_expected = {"top429_ip": "198.51.100.44"}
    assert answer_matches("top_429_ip", ip_expected, "IP: 198.51.100.44.")
    assert not answer_matches("top_429_ip", ip_expected, "198.51.100.440")

    route_expected = {"top503_route": "accounts"}
    assert answer_matches("top_503_route", route_expected, "Route: accounts.")
    assert not answer_matches("top_503_route", route_expected, "accounts-v2")

    line_expected = {"line_request": "GET /api/payments"}
    assert answer_matches(
        "line_request",
        line_expected,
        "GET /api/payments [L1]",
    )
    assert not answer_matches(
        "line_request",
        line_expected,
        "GET /api/payments",
    )
    assert not answer_matches(
        "line_request",
        line_expected,
        "GET /api/paymentsx [L1]",
    )


def test_refusal_comparator_requires_exact_normalized_text():
    expected = {}
    assert answer_matches("refusal", expected, "No verified data")
    assert not answer_matches("refusal", expected, "No verified data.")
