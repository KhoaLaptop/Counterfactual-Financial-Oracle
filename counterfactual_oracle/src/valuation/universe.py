"""
Stock universes for the ranker: a user watchlist, or a dated S&P 500 snapshot.

    python -m counterfactual_oracle.src.valuation.universe --refresh-sp500

rewrites data/universe/sp500.csv from Wikipedia's constituents table.
"""

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

SP500_CSV = Path(__file__).resolve().parents[2] / "data" / "universe" / "sp500.csv"
SP500_SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


@dataclass
class Universe:
    name: str
    tickers: List[str]
    as_of: Optional[str] = None
    sectors: Dict[str, str] = field(default_factory=dict)


def normalize_ticker(ticker: str) -> str:
    """SEC and Yahoo write share classes with a dash: BRK.B -> BRK-B."""
    return ticker.strip().upper().replace(".", "-")


def load_watchlist(path) -> List[str]:
    """One ticker per line; '#' starts a comment; duplicates are dropped (first wins)."""
    tickers: List[str] = []
    for line in Path(path).read_text().splitlines():
        ticker = normalize_ticker(line.split("#", 1)[0])
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def load_sp500(path=SP500_CSV) -> Universe:
    lines = Path(path).read_text().splitlines()
    as_of = None
    if lines and lines[0].startswith("#"):
        meta = dict(part.strip().split(": ", 1) for part in lines[0].lstrip("# ").split(",") if ": " in part)
        as_of = meta.get("as_of")
        lines = lines[1:]
    rows = list(csv.DictReader(lines))
    return Universe(
        name="sp500",
        tickers=[row["ticker"] for row in rows],
        as_of=as_of,
        sectors={row["ticker"]: row["sector"] for row in rows},
    )


class _ConstituentsParser(HTMLParser):
    """Collects the cell text of the table with id="constituents"."""

    def __init__(self):
        super().__init__()
        self.depth = 0  # nesting depth inside the constituents table (0 = outside)
        self.rows: List[List[str]] = []
        self.cell: Optional[List[str]] = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.depth or dict(attrs).get("id") == "constituents":
                self.depth += 1
        elif self.depth == 1 and tag == "tr":
            self.rows.append([])
        elif self.depth == 1 and tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self.cell is not None:
            self.rows[-1].append("".join(self.cell).strip())
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def parse_sp500_html(html: str) -> List[Tuple[str, str, str]]:
    """(ticker, name, sector) rows from Wikipedia's S&P 500 constituents table."""
    parser = _ConstituentsParser()
    parser.feed(html)
    header, *rows = [r for r in parser.rows if r]
    col = {name: i for i, name in enumerate(header)}
    return [
        (normalize_ticker(r[col["Symbol"]]), r[col["Security"]], r[col["GICS Sector"]])
        for r in rows if len(r) >= len(header)
    ]


def refresh_sp500(fetch_text: Callable[[str], str], path=SP500_CSV, today: Optional[date] = None) -> int:
    rows = parse_sp500_html(fetch_text(SP500_SOURCE_URL))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        f.write(f"# as_of: {(today or date.today()).isoformat()}, source: {SP500_SOURCE_URL}\n")
        writer = csv.writer(f)
        writer.writerow(["ticker", "name", "sector"])
        writer.writerows(rows)
    return len(rows)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage ranker universes.")
    parser.add_argument("--refresh-sp500", action="store_true", help=f"Rewrite {SP500_CSV.name} from Wikipedia")
    args = parser.parse_args(argv)
    if not args.refresh_sp500:
        parser.error("nothing to do: pass --refresh-sp500")

    import requests

    def fetch_text(url: str) -> str:
        response = requests.get(url, headers={"User-Agent": "CounterfactualOracle/1.0"}, timeout=30)
        response.raise_for_status()
        return response.text

    count = refresh_sp500(fetch_text)
    print(f"Wrote {count} constituents to {SP500_CSV}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
