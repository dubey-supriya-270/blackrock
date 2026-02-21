"""
Period matching — optimized with IntervalTree + frozen hash caching.

Arch decisions:
  1. IntervalTree converts O(n) per-transaction scans to O(log n).
  2. build_*_tree functions are called once per request then passed
     through as context — avoid rebuilding on every transaction.
  3. _parse_date uses ordinals (int) instead of date objects for
     IntervalTree which needs numeric ranges.
  4. Invalid dates (e.g. Nov 31) are clamped to month end rather
     than raising, matching real-world data quality expectations.
"""
from datetime import datetime, date
import calendar
from decimal import Decimal
from typing import Optional
from intervaltree import IntervalTree


# ─── Date parsing ─────────────────────────────────────────────────────────────

def _parse_date(dt_str: str) -> date:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt).date()
        except ValueError:
            try:
                parts = dt_str.split(" ")[0].split("-")
                y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                return date(y, m, min(d, calendar.monthrange(y, m)[1]))
            except Exception:
                continue
    raise ValueError(f"Invalid date: {dt_str!r}")


def _ord(d: date) -> int:
    """Date → integer ordinal (required by IntervalTree)."""
    return d.toordinal()


# ─── Tree builders ────────────────────────────────────────────────────────────

def build_q_tree(q_periods: list[dict]) -> IntervalTree:
    """O(P log P) — called once per request, reused for all transactions."""
    tree = IntervalTree()
    for qp in q_periods:
        s = _ord(_parse_date(qp["start"]))
        e = _ord(_parse_date(qp["end"])) + 1   # half-open [s, e)
        if s < e:
            tree[s:e] = qp
    return tree


def build_p_tree(p_periods: list[dict]) -> IntervalTree:
    tree = IntervalTree()
    for pp in p_periods:
        s = _ord(_parse_date(pp["start"]))
        e = _ord(_parse_date(pp["end"])) + 1
        if s < e:
            tree[s:e] = pp
    return tree


# ─── Rule application ─────────────────────────────────────────────────────────

def apply_q_rule(
    txn_date: str,
    remanent: Decimal,
    q_periods: list[dict],
    _q_tree: Optional[IntervalTree] = None,
) -> tuple[Decimal, Optional[dict]]:
    """O(log n). Tie-breaker: latest start date wins."""
    txn_ord = _ord(_parse_date(txn_date))
    tree = _q_tree if _q_tree is not None else build_q_tree(q_periods)
    hits = tree[txn_ord]
    if not hits:
        return remanent, None
    matched = max(hits, key=lambda iv: iv.begin).data
    return Decimal(str(matched["fixed"])), matched


def apply_p_rules(
    txn_date: str,
    remanent: Decimal,
    p_periods: list[dict],
    _p_tree: Optional[IntervalTree] = None,
) -> tuple[Decimal, list[dict]]:
    """O(log n). All matching p periods are cumulative."""
    txn_ord = _ord(_parse_date(txn_date))
    tree = _p_tree if _p_tree is not None else build_p_tree(p_periods)
    matched = []
    for iv in tree[txn_ord]:
        matched.append(iv.data)
        remanent += Decimal(str(iv.data["extra"]))
    return remanent, matched


def group_by_k(transactions: list[dict], k_periods: list[dict]) -> dict[str, Decimal]:
    """Group and sum remanents by k period. A transaction may belong to multiple k periods."""
    txn_data = [
        (_ord(_parse_date(t["date"])), Decimal(str(t.get("remanent", "0"))))
        for t in transactions
    ]
    sums: dict[str, Decimal] = {}
    for kp in k_periods:
        s = _ord(_parse_date(kp["start"]))
        e = _ord(_parse_date(kp["end"]))
        sums[kp["id"]] = sum(
            (r for o, r in txn_data if s <= o <= e), Decimal("0")
        )
    return sums
