"""Structural validation of the exported M3 workflows (stdlib only).

Run: python n8n/workflows/validate.py
This is the reproducible, offline half of the M3 fake-payload test: it proves
the router branches on alertname, each handler calls the Advisor through Kong
with the apikey header, and both handlers post to the notification channel.
The live half is the webhook curl in README.md.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "00-alert-router.json": "00 Alert Router",
    "10-circuit-open.json": "10 Circuit Open Handler",
    "20-429-spike.json": "20 429 Spike Handler",
}


def load(name):
    path = HERE / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["name"] == EXPECTED[name], f"{name}: unexpected workflow name"
    assert data.get("active") is True, f"{name}: workflow must be active"
    return data


def nodes(data):
    return {node["name"]: node for node in data["nodes"]}


def test_router():
    data = load("00-alert-router.json")
    by_name = nodes(data)

    assert by_name["Webhook"]["parameters"]["path"] == "alertmanager"
    assert by_name["Webhook"]["parameters"]["httpMethod"] == "POST"

    switch = by_name["Switch on alertname"]["parameters"]
    assert switch["mode"] == "expression"
    expression = switch["output"]
    for alertname in ["KongCircuitOpen", "Kong429Spike", "KongUpstreamTargetUnhealthy"]:
        assert f"'{alertname}'" in expression
    assert "? 0" in expression and "? 1" in expression

    connections = data["connections"]["Switch on alertname"]["main"]
    targets = [entry[0]["node"] for entry in connections]
    assert targets == ["Call circuit-open workflow", "Call 429 workflow"]
    assert "webhook/circuit-open" in by_name["Call circuit-open workflow"]["parameters"]["url"]
    assert "webhook/429" in by_name["Call 429 workflow"]["parameters"]["url"]


def check_handler(name, webhook_path, question_marker):
    data = load(name)
    by_name = nodes(data)

    assert by_name["Webhook"]["parameters"]["path"] == webhook_path
    assert question_marker in by_name["Build advisor question"]["parameters"]["jsCode"]

    advisor = by_name["Advisor via Kong (apikey)"]["parameters"]
    assert advisor["url"] == "={{ $env.ADVISOR_URL }}"
    assert advisor["method"] == "POST"
    assert advisor["jsonBody"] == "={{ JSON.stringify({ question: $json.question }) }}"
    headers = {h["name"]: h["value"] for h in advisor["headerParameters"]["parameters"]}
    assert headers["apikey"] == "={{ $env.ADVISOR_APIKEY }}"
    assert by_name["Advisor via Kong (apikey)"]["onError"] == "continueRegularOutput"

    notify = by_name["Post to channel"]["parameters"]
    assert notify["url"].startswith("={{ $env.TELEGRAM_API_BASE }}/bot")
    assert notify["url"].endswith("/sendMessage")

    chain = [
        by_name[n]["parameters"] or n
        for n in ["Webhook", "Build advisor question", "Advisor via Kong (apikey)",
                  "Format notification", "Post to channel"]
    ]
    assert len(chain) == 5
    for source, target in [
        ("Webhook", "Build advisor question"),
        ("Build advisor question", "Advisor via Kong (apikey)"),
        ("Advisor via Kong (apikey)", "Format notification"),
        ("Format notification", "Post to channel"),
    ]:
        assert data["connections"][source]["main"][0][0]["node"] == target


def test_handlers():
    check_handler("10-circuit-open.json", "circuit-open", "circuit-open alert")
    check_handler("20-429-spike.json", "429", "HTTP 429 spike")


if __name__ == "__main__":
    test_router()
    test_handlers()
    print("M3 workflow structure OK (router + 2 handlers)")
