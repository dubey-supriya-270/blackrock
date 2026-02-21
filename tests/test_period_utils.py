from decimal import Decimal
import pytest
from app.core.period_utils import apply_q_rule, apply_p_rules, group_by_k


Q_PERIODS = [
    {"id": "q1", "start": "2024-01-01", "end": "2024-01-31", "fixed": "200"},
    {"id": "q2", "start": "2024-01-15", "end": "2024-01-31", "fixed": "150"},  # later start
]

P_PERIODS = [
    {"id": "p1", "start": "2024-01-01", "end": "2024-01-31", "extra": "50"},
    {"id": "p2", "start": "2024-01-20", "end": "2024-02-20", "extra": "75"},
]

K_PERIODS = [
    {"id": "k1", "start": "2024-01-01", "end": "2024-01-31"},
    {"id": "k2", "start": "2024-01-15", "end": "2024-02-15"},
]

TRANSACTIONS = [
    {"date": "2024-01-10 09:00:00", "remanent": "80"},   # in k1 only
    {"date": "2024-01-20 09:00:00", "remanent": "60"},   # in k1 and k2
    {"date": "2024-02-01 09:00:00", "remanent": "40"},   # in k2 only
]


# --- q period tests ---

def test_q_rule_tie_breaker_latest_start():
    """Should pick q2 (start 2024-01-15) over q1 (start 2024-01-01) for 2024-01-20."""
    new_rem, matched = apply_q_rule("2024-01-20 09:00:00", Decimal("80"), Q_PERIODS)
    assert matched["id"] == "q2"
    assert new_rem == Decimal("150")


def test_q_rule_only_one_matches():
    """Only q1 matches for 2024-01-05."""
    new_rem, matched = apply_q_rule("2024-01-05 09:00:00", Decimal("80"), Q_PERIODS)
    assert matched["id"] == "q1"
    assert new_rem == Decimal("200")


def test_q_rule_no_match():
    new_rem, matched = apply_q_rule("2024-03-01 09:00:00", Decimal("80"), Q_PERIODS)
    assert matched is None
    assert new_rem == Decimal("80")


# --- p period tests ---

def test_p_rule_single_match():
    """Only p1 applies for 2024-01-10."""
    new_rem, matched = apply_p_rules("2024-01-10 09:00:00", Decimal("80"), P_PERIODS)
    assert len(matched) == 1
    assert matched[0]["id"] == "p1"
    assert new_rem == Decimal("130")  # 80 + 50


def test_p_rule_cumulative():
    """Both p1 and p2 apply for 2024-01-25 — cumulative."""
    new_rem, matched = apply_p_rules("2024-01-25 09:00:00", Decimal("80"), P_PERIODS)
    assert len(matched) == 2
    assert new_rem == Decimal("205")  # 80 + 50 + 75


def test_p_rule_no_match():
    new_rem, matched = apply_p_rules("2024-03-01 09:00:00", Decimal("80"), P_PERIODS)
    assert len(matched) == 0
    assert new_rem == Decimal("80")


# --- k period grouping tests ---

def test_k_group_transaction_in_one_k():
    """2024-01-10 is only in k1."""
    sums = group_by_k([TRANSACTIONS[0]], K_PERIODS)
    assert sums["k1"] == Decimal("80")
    assert sums["k2"] == Decimal("0")


def test_k_group_transaction_in_both_k():
    """2024-01-20 belongs to both k1 and k2."""
    sums = group_by_k([TRANSACTIONS[1]], K_PERIODS)
    assert sums["k1"] == Decimal("60")
    assert sums["k2"] == Decimal("60")


def test_k_group_all_transactions():
    sums = group_by_k(TRANSACTIONS, K_PERIODS)
    # k1: 80 + 60 = 140
    # k2: 60 + 40 = 100
    assert sums["k1"] == Decimal("140")
    assert sums["k2"] == Decimal("100")
