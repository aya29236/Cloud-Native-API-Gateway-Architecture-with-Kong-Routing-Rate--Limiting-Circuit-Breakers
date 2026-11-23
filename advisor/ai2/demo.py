"""Scripted and optional live AI2 demonstrations."""

import argparse

from advisor.ai1.generator import generate_synthetic_logs
from advisor.ai1.reader import read_kong_log_text

from .agent import analyze
from .llm import OllamaClient, ScriptedClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    text, _raw, _expected = generate_synthetic_logs()
    records = read_kong_log_text(text).records

    if args.live:
        try:
            clients = [
                OllamaClient(),
                OllamaClient(),
            ]
            live_names = ["live question 1", "live question 2"]
        except RuntimeError as exc:
            print(exc)
            return
    else:
        clients = [
            ScriptedClient(
                [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "top_ips",
                                    "arguments": {"limit": 3},
                                }
                            }
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": "The top IP is 198.51.100.44.",
                    },
                ]
            ),
            ScriptedClient(
                [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "top_routes",
                                    "arguments": {"limit": 3},
                                }
                            }
                        ],
                    },
                    {
                        "role": "assistant",
                        "content": "The top route is payments.",
                    },
                ]
            ),
        ]
        live_names = []

    questions = [
        "Which IP has the most 429 responses?",
        "Which route has the most 503 responses?",
    ]
    for index, (question, client) in enumerate(zip(questions, clients), start=1):
        response = analyze(question, records, client)
        print(f"\nQuestion {index}: {question}")
        print("Answer:", response.summary)
        print("Citations:", response.citations)
        print("Verified:", response.verified)
        print("Tool trace:")
        for trace in response.tool_trace:
            print(" ", trace)


if __name__ == "__main__":
    main()
