"""Gate 0 Ollama tool-calling spike."""

from .llm import OllamaClient
from .agent import analyze
from .schemas import build_tool_definitions
from advisor.ai1.generator import generate_synthetic_logs
from advisor.ai1.reader import read_kong_log_text


def main() -> None:
    import os

    if not os.getenv("ADVISOR_MODEL"):
        print("Ollama spike skipped: set ADVISOR_MODEL to an installed Ollama model.")
        return

    try:
        client = OllamaClient()
        text, _raw, _expected = generate_synthetic_logs(seed=2026)
        records = read_kong_log_text(text).records
        tools = build_tool_definitions()
        message = client.chat(
            [
                {"role": "system", "content": "Call exactly one read-only tool for a simple test."},
                {"role": "user", "content": "Use top_ips with limit 1."},
            ],
            tools,
        )
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            call = tool_calls[0]
            function = call.get("function", {})
            print(
                "Valid tool call:",
                function.get("name"),
                function.get("arguments", {}),
            )
        else:
            print("No tool call returned.")

        response = analyze(
            "Use top_ips with limit 1, then answer concisely.",
            records,
            OllamaClient(),
        )
        print("Final answer:", response.summary)
    except Exception as exc:
        print(f"Ollama spike unavailable: {exc}")


if __name__ == "__main__":
    main()
