#!/usr/bin/env python3
"""Convert the Google-Sheets roster CSV exports into the tab-separated raw
format that parse_history.py expects.

Usage:
    python3 csv_to_raw.py <2025-roster.csv> <2026-roster.csv> <out.txt>

The 2025 roster sheet actually spans Jul 2024 -> Dec 2025, split by a
"↓2025↓" marker row. The 2026 sheet is Jan -> Dec 2026.

Section markers written into the output (parse_history.py keys off these):
    # 2026     -> 2026 services
    # 2025     -> despite the label, the 2024 half of the 2025 sheet
    ↓2025↓    -> the 2025 half
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# Services after this date are future/unfilled — not history.
TODAY = date(2026, 8, 15)


def drop_leading_blank(row: list[str]) -> list[str]:
    """Sheets exports carry an empty spacer column A."""
    return row[1:] if row and row[0] == "" else row


def rstrip_empty(cells: list[str]) -> list[str]:
    while cells and cells[-1].strip() == "":
        cells.pop()
    return cells


def to_line(cells: list[str]) -> str:
    # Newlines inside a cell would break the line-oriented parser.
    cells = [c.replace("\n", " ").replace("\t", " ") for c in cells]
    return "\t".join(rstrip_empty(list(cells)))


def parse_day_month(label: str) -> tuple[int, int] | None:
    """'7 Jul' / '3 Apr (Good Friday)' / '25 Dec (Christmas)' -> (day, month)."""
    parts = label.strip().split()
    if len(parts) < 2:
        return None
    try:
        day = int(parts[0])
    except ValueError:
        return None
    mon = MONTHS.get(parts[1][:3].lower())
    if mon is None:
        return None
    return day, mon


def load_blocks(path: Path, max_cols: int) -> tuple[list[list[list[str]]], int]:
    """Split a roster CSV into service blocks.

    Returns (blocks, split_index) where split_index is the block index at which
    the '↓2025↓' marker appeared (len(blocks) if it never did).
    """
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))

    blocks: list[list[list[str]]] = []
    current: list[list[str]] | None = None
    split_index = None

    for row in rows:
        cells = drop_leading_blank(row)[:max_cols]
        joined = "".join(cells).strip()

        if joined.startswith("↓2025↓"):
            split_index = len(blocks)
            continue
        if not joined:
            continue
        if cells[0].strip() == "Date":
            current = [cells]
            blocks.append(current)
            continue
        if current is not None:
            current.append(cells)

    return blocks, (split_index if split_index is not None else len(blocks))


def emit(blocks: list[list[list[str]]], year: int, out: list[str]) -> int:
    kept = 0
    for block in blocks:
        dm = parse_day_month(block[0][1] if len(block[0]) > 1 else "")
        if dm:
            day, mon = dm
            try:
                if date(year, mon, day) > TODAY:
                    continue  # future service, not history
            except ValueError:
                pass
        for cells in block:
            out.append(to_line(cells))
        out.append("")
        kept += 1
    return kept


def main() -> None:
    csv_2025, csv_2026, out_path = (Path(a) for a in sys.argv[1:4])

    # 2025 sheet has a second frequency table pasted in cols G-H — cut it off.
    blocks_25, split = load_blocks(csv_2025, max_cols=6)
    blocks_26, _ = load_blocks(csv_2026, max_cols=6)

    out: list[str] = [
        f"# Rebuilt from roster CSV exports on {TODAY.isoformat()}",
        "# Format: tab-separated rows. Each service block starts with a "
        '"Date" row, then Theme/Songs rows.',
        "",
        "# 2026",
        "",
    ]
    n26 = emit(blocks_26, 2026, out)

    out += ["# 2025", ""]  # label is historical; content is 2024
    n24 = emit(blocks_25[:split], 2024, out)

    out += ["↓2025↓\t↓2025↓\t↓2025↓", ""]
    n25 = emit(blocks_25[split:], 2025, out)

    Path(out_path).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"2024: {n24} services | 2025: {n25} | 2026: {n26} -> {out_path}")


if __name__ == "__main__":
    main()
