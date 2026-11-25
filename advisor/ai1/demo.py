"""Print deterministic AI1 synthetic-log analysis tables."""

from .generator import generate_synthetic_logs
from .reader import read_kong_log_text
from .tools import (
    consumer_stats,
    get_log_lines,
    status_breakdown,
    time_range,
    top_ip_route_pairs,
    top_ips,
    top_routes,
)


def _print_table(title: str, columns: tuple[str, ...], rows: list[dict]) -> None:
    print(f"\n{title}")
    widths = [max(len(column), *(len(str(row[column])) for row in rows)) for column in columns] if rows else [len(column) for column in columns]
    print("  ".join(column.ljust(width) for column, width in zip(columns, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(row[column]).ljust(width) for column, width in zip(columns, widths)))


def main() -> None:
    text, _raw_records, expected = generate_synthetic_logs()
    result = read_kong_log_text(text)
    records = result.records

    print("AI1 synthetic log demo")
    print(
        f"Reader counts: valid={result.valid_count} "
        f"blank={result.blank_count} malformed={result.malformed_count}"
    )
    print(f"Expected counts: {expected}")

    status = status_breakdown(records)
    _print_table(
        "status_breakdown",
        ("status", "count"),
        [{"status": key, "count": value} for key, value in status.items()],
    )
    _print_table("top_ips", ("client_ip", "count"), top_ips(records))
    _print_table("top_routes", ("route", "count"), top_routes(records))
    _print_table(
        "top_ip_route_pairs",
        ("client_ip", "route", "count"),
        top_ip_route_pairs(records),
    )
    _print_table("consumer_stats", ("consumer", "count"), consumer_stats(records))

    selected = time_range(records, 1000, 1009)
    _print_table(
        "time_range",
        ("line_id", "started_at", "client_ip"),
        [
            {
                "line_id": item.line_id,
                "started_at": item.record.started_at,
                "client_ip": item.record.client_ip,
            }
            for item in selected
        ],
    )
    _print_table(
        "get_log_lines",
        ("line_id", "line_number"),
        [
            {"line_id": row["line_id"], "line_number": row["line_number"]}
            for row in get_log_lines(records)
        ],
    )


if __name__ == "__main__":
    main()
