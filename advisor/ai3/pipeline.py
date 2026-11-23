"""AI2 loop wrapped in AI3 verification and a one-retry budget."""

from collections.abc import Sequence
from typing import Any

from advisor.ai1.models import ParsedLogRecord
from advisor.ai2.agent import AnalyzeResponse, analyze, save_trace
from advisor.ai2.llm import LLMClient

from .verifier import VerificationReport, verify_answer


def _unsupported_feedback(report: VerificationReport) -> str:
    details = "; ".join(
        f"{issue.kind}:{issue.value} ({issue.reason})"
        for issue in report.issues
    )
    return (
        "<verifier_feedback>\n"
        f"The previous answer was unsupported: {details}\n"
        "Answer only from tool results or reply exactly: No verified data\n"
        "</verifier_feedback>"
    )


def analyze_verified_detailed(
    question: str,
    records: Sequence[ParsedLogRecord],
    client: LLMClient,
    max_steps: int = 6,
    save: bool = True,
) -> tuple[AnalyzeResponse, VerificationReport, bool, int]:
    """Run AI2 once, retry once, and return response plus AI3 metadata."""
    delivered, report, retry_used, attempt_count, _first_report = (
        _analyze_verified_with_reports(
            question,
            records,
            client,
            max_steps,
            save,
        )
    )
    return delivered, report, retry_used, attempt_count


def _analyze_verified_with_reports(
    question: str,
    records: Sequence[ParsedLogRecord],
    client: LLMClient,
    max_steps: int,
    save: bool,
) -> tuple[AnalyzeResponse, VerificationReport, bool, int, VerificationReport]:
    first = analyze(question, records, client, max_steps=max_steps)
    first_report = verify_answer(first.summary, first)

    if first_report.ok:
        delivered = first.model_copy(update={"verified": True})
        attempt_count = 1
        retry_used = False
        if save:
            save_trace(
                delivered,
                extra={
                    "verifier_report": first_report.model_dump(),
                    "verifier_reports": [first_report.model_dump()],
                    "attempt_count": attempt_count,
                    "retry_used": retry_used,
                    "fallback": False,
                },
            )
        return delivered, first_report, retry_used, attempt_count, first_report

    used_tool_calls = len(first.tool_trace)
    retry_used = used_tool_calls < max_steps
    if not retry_used:
        delivered = first.model_copy(
            update={"summary": "No verified data", "verified": True}
        )
        attempt_count = 1
        refusal_report = verify_answer(delivered.summary, delivered)
        if save:
            save_trace(
                delivered,
                extra={
                    "verifier_report": refusal_report.model_dump(),
                    "verifier_reports": [
                        first_report.model_dump(),
                        refusal_report.model_dump(),
                    ],
                    "attempt_count": attempt_count,
                    "retry_used": retry_used,
                    "fallback": True,
                },
            )
        return delivered, refusal_report, retry_used, attempt_count, first_report

    remaining = max_steps - used_tool_calls
    retry_question = (
        f"{question}\n\n{_unsupported_feedback(first_report)}"
    )
    second = analyze(
        retry_question,
        records,
        client,
        max_steps=remaining,
    )

    combined_trace = list(first.tool_trace)
    for trace in second.tool_trace:
        copy_trace = dict(trace)
        copy_trace["step"] = len(combined_trace) + 1
        combined_trace.append(copy_trace)
    combined_stats: dict[str, Any] = dict(first.stats)
    combined_stats.update(second.stats)

    combined_response = second.model_copy(
        update={
            "stats": combined_stats,
            "tool_trace": combined_trace,
        }
    )
    second_report = verify_answer(second.summary, combined_response)
    if second_report.ok:
        delivered = second.model_copy(
            update={
                "stats": combined_stats,
                "tool_trace": combined_trace,
                "verified": True,
            }
        )
        delivered_report = second_report
        fallback = False
    else:
        delivered = second.model_copy(
            update={
                "summary": "No verified data",
                "stats": combined_stats,
                "citations": [],
                "tool_trace": combined_trace,
                "verified": True,
            }
        )
        delivered_report = verify_answer(delivered.summary, delivered)
        fallback = True

    attempt_count = 2
    if save:
        save_trace(
            delivered,
            extra={
                "verifier_report": delivered_report.model_dump(),
                "verifier_reports": [
                    first_report.model_dump(),
                    second_report.model_dump(),
                ],
                "attempt_count": attempt_count,
                "retry_used": True,
                "fallback": fallback,
            },
        )
    return delivered, delivered_report, True, attempt_count, first_report


def analyze_verified(
    question: str,
    records: Sequence[ParsedLogRecord],
    client: LLMClient,
    max_steps: int = 6,
) -> AnalyzeResponse:
    response, _report, _retry_used, _attempt_count = analyze_verified_detailed(
        question,
        records,
        client,
        max_steps=max_steps,
    )
    return response
