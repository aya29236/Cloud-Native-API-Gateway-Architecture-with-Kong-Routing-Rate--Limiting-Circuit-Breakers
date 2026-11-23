import copy
import io
import json
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from advisor.ai1.generator import generate_synthetic_logs
from advisor.ai1.reader import read_kong_log_text
from advisor.ai2.agent import (
    MAX_STEPS,
    AnalyzeResponse,
    _arguments_dict,
    analyze,
    save_trace,
)
from advisor.ai2.llm import OllamaClient, ScriptedClient
from advisor.ai2.prompts import SYSTEM_PROMPT, tool_result_message
from advisor.ai2.schemas import DESCRIPTIONS, TOOL_REGISTRY, build_tool_definitions


def records():
    text, _raw, _expected = generate_synthetic_logs(seed=2026)
    return read_kong_log_text(text).records


def tool_call(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": name,
                    "arguments": arguments,
                }
            }
        ],
    }


def test_two_questions_have_different_traces():
    parsed = records()
    first = analyze(
        "Which IP?",
        parsed,
        ScriptedClient(
            [
                tool_call("top_ips", {"limit": 1}),
                {"role": "assistant", "content": "198.51.100.44"},
            ],
        ),
    )
    second = analyze(
        "Which route?",
        parsed,
        ScriptedClient(
            [
                tool_call("top_routes", {"limit": 1}),
                {"role": "assistant", "content": "payments"},
            ],
        ),
    )
    assert [item["tool"] for item in first.tool_trace] == ["top_ips"]
    assert [item["tool"] for item in second.tool_trace] == ["top_routes"]
    assert first.tool_trace != second.tool_trace


def test_identical_normalized_tool_call_reuses_result_and_counts_as_step():
    class CapturingScriptedClient(ScriptedClient):
        def __init__(self, messages):
            super().__init__(messages)
            self.received_messages = []

        def chat(self, messages, tools):
            self.received_messages.append(copy.deepcopy(list(messages)))
            return super().chat(messages, tools)

    client = CapturingScriptedClient(
        [
            tool_call("top_ips", {"limit": 1}),
            tool_call(
                "top_ips",
                {
                    "end_at": None,
                    "limit": 1,
                    "status": None,
                    "start_at": None,
                },
            ),
            {"role": "assistant", "content": "198.51.100.44"},
        ]
    )
    response = analyze("Which IP?", records(), client)

    assert [entry["step"] for entry in response.tool_trace] == [1, 2]
    assert [entry["tool"] for entry in response.tool_trace] == ["top_ips", "top_ips"]
    assert response.tool_trace[0]["result_summary"] == response.tool_trace[1]["result_summary"]
    assert response.tool_trace[1]["note"] == "duplicate call: answer now"
    assert "duplicate call: answer now" in client.received_messages[2][-1]["content"]


def test_tool_schemas_are_valid_json_schema_and_match_models():
    definitions = build_tool_definitions()
    assert len(definitions) == 7
    names = {definition["function"]["name"] for definition in definitions}
    assert names == set(TOOL_REGISTRY)
    for definition in definitions:
        function = definition["function"]
        assert definition["type"] == "function"
        assert "read-only" in function["description"].lower()
        assert function["parameters"]["type"] == "object"
        model = TOOL_REGISTRY[function["name"]][0]
        assert set(function["parameters"]["properties"]) == set(model.model_fields)


def test_unknown_tool_and_invalid_arguments_continue_and_are_traced():
    parsed = records()
    client = ScriptedClient(
        [
            tool_call("unknown_tool", {"limit": 1}),
            tool_call("top_ips", {"limit": "bad"}),
            {"role": "assistant", "content": "No verified data"},
        ],
    )
    response = analyze("test errors", parsed, client)
    assert len(response.tool_trace) == 2
    assert "unknown tool" in response.tool_trace[0]["error"]
    assert "invalid arguments" in response.tool_trace[1]["error"]
    assert response.summary == "No verified data"


def test_extra_arguments_are_rejected_before_tool_execution():
    parsed = records()
    client = ScriptedClient(
        [
            tool_call("top_ips", {"limit": 1, "unexpected": True}),
            {"role": "assistant", "content": "No verified data"},
        ]
    )
    response = analyze("reject extra", parsed, client)
    assert len(response.tool_trace) == 1
    assert "invalid arguments" in response.tool_trace[0]["error"]


@pytest.mark.parametrize("value", [None, 42, ["limit", 1]])
def test_non_dict_non_string_tool_arguments_return_empty_dict(value):
    assert _arguments_dict(value) == {}


def test_step_cap_stops_at_exactly_six_calls():
    parsed = records()
    client = ScriptedClient(
        [
            tool_call("top_ips", {"limit": 1})
            for _ in range(MAX_STEPS + 2)
        ]
    )
    response = analyze("keep calling", parsed, client, max_steps=MAX_STEPS)
    assert len(response.tool_trace) == 6
    assert all(item["step"] == index for index, item in enumerate(response.tool_trace, 1))
    assert response.summary == "No verified data"


def test_text_answer_without_calls_passes_through():
    parsed = records()
    response = analyze(
        "answer directly",
        parsed,
        ScriptedClient([{"role": "assistant", "content": "203.0.113.77"}]),
    )
    assert response.summary == "203.0.113.77"

    fallback = analyze(
        "answer none",
        parsed,
        ScriptedClient([{"role": "assistant", "content": "  "}]),
    )
    assert fallback.summary == "No verified data"


def test_prompt_injection_remains_delimited_tool_data():
    text, _raw, _expected = generate_synthetic_logs()
    parsed = read_kong_log_text(text).records

    class CapturingClient:
        def __init__(self):
            self.messages = None

        def chat(self, messages, tools):
            del tools
            self.messages = list(messages)
            return tool_call("get_log_lines", {"limit": 20})

    client = CapturingClient()
    response = analyze("show logs", parsed, client)
    injection_seen = False
    for message in client.messages or []:
        if message.get("role") == "tool":
            content = message["content"]
            assert content.startswith('<tool_result name="get_log_lines">')
            assert "</tool_result>" in content
            assert "untrusted data" in content
            if "Ignore previous instructions" in content:
                injection_seen = True
    assert injection_seen
    assert response.tool_trace[0]["tool"] == "get_log_lines"


def test_analyze_does_not_modify_records():
    parsed = records()
    before = [item.model_dump() for item in parsed]
    analyze(
        "count",
        parsed,
        ScriptedClient(
            [
                tool_call("status_breakdown", {}),
                {"role": "assistant", "content": "No verified data"},
            ],
        ),
    )
    assert [item.model_dump() for item in parsed] == before


def test_analyze_response_has_exact_c1_fields():
    response = AnalyzeResponse(
        summary="No verified data",
        stats={},
        citations=[],
        tool_trace=[],
        verified=False,
    )
    assert set(type(response).model_fields) == {
        "summary",
        "stats",
        "citations",
        "tool_trace",
        "verified",
    }
    assert set(response.model_dump()) == {
        "summary",
        "stats",
        "citations",
        "tool_trace",
        "verified",
    }
    assert response.verified is False


def test_citations_are_captured_from_answer():
    parsed = records()
    response = analyze(
        "cite",
        parsed,
        ScriptedClient(
            [
                tool_call("get_log_lines", {"limit": 2}),
                {
                    "role": "assistant",
                    "content": "Observed [L1] and [L2]; repeated [L1].",
                },
            ],
        ),
    )
    assert response.citations == ["[L1]", "[L2]"]


class MockUrlResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_ollama_request_temperature_tools_and_model(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return MockUrlResponse(
            {"message": {"role": "assistant", "content": "done"}}
        )

    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.test:11434")
    monkeypatch.setenv("ADVISOR_MODEL", "test-model")
    client = OllamaClient(timeout=7)

    with patch("advisor.ai2.llm.urllib.request.urlopen", fake_urlopen):
        message = client.chat(
            [{"role": "user", "content": "test"}],
            build_tool_definitions(),
        )

    assert message["content"] == "done"
    payload = json.loads(captured["request"].data)
    assert captured["request"].full_url == "http://ollama.test:11434/api/chat"
    assert captured["timeout"] == 7
    assert payload["model"] == "test-model"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["tools"] == build_tool_definitions()


def test_ollama_timeout_uses_environment_default(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["timeout"] = timeout
        return MockUrlResponse(
            {"message": {"role": "assistant", "content": "done"}}
        )

    monkeypatch.setenv("ADVISOR_MODEL", "test-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT", "12.5")
    client = OllamaClient()
    with patch("advisor.ai2.llm.urllib.request.urlopen", fake_urlopen):
        client.chat([], [])
    assert captured["timeout"] == 12.5


def test_ollama_timeout_defaults_to_180_seconds(monkeypatch):
    monkeypatch.setenv("ADVISOR_MODEL", "test-model")
    monkeypatch.delenv("OLLAMA_TIMEOUT", raising=False)
    assert OllamaClient().timeout == 180


@pytest.mark.parametrize("value", ["not-a-number", "0", "-1", "inf"])
def test_ollama_timeout_rejects_invalid_environment_values(monkeypatch, value):
    monkeypatch.setenv("ADVISOR_MODEL", "test-model")
    monkeypatch.setenv("OLLAMA_TIMEOUT", value)
    with pytest.raises(RuntimeError, match="OLLAMA_TIMEOUT"):
        OllamaClient()


def test_ollama_missing_model_raises_clear_error(monkeypatch):
    monkeypatch.delenv("ADVISOR_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="ADVISOR_MODEL"):
        OllamaClient()


def test_ollama_network_error_is_controlled(monkeypatch):
    monkeypatch.setenv("ADVISOR_MODEL", "test-model")

    def unreachable(request, timeout):
        del request, timeout
        raise TimeoutError("server unavailable")

    client = OllamaClient(host="http://127.0.0.1:9")
    with patch("advisor.ai2.llm.urllib.request.urlopen", unreachable):
        with pytest.raises(RuntimeError, match="timed out"):
            client.chat([], [])


def test_system_prompt_contains_tool_selection_and_citation_rules():
    assert "Pick the tool that matches the question" in SYSTEM_PROMPT
    assert "status-specific questions use the status filter" in SYSTEM_PROMPT
    assert "Never call the same tool with the same arguments twice" in SYSTEM_PROMPT
    assert "After the tool results arrive, write the final answer" in SYSTEM_PROMPT
    assert "When quoting a log line, cite [L<id>]" in SYSTEM_PROMPT
    for name in ("top_ips", "top_routes", "top_ip_route_pairs", "consumer_stats"):
        assert "only count records with this HTTP status" in DESCRIPTIONS[name]


def test_save_trace_writes_json(tmp_path):
    response = AnalyzeResponse(
        summary="No verified data",
        stats={},
        citations=[],
        tool_trace=[],
        verified=False,
    )
    path = save_trace(response, str(tmp_path))
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["response"]["summary"] == "No verified data"
