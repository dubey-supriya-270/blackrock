from decimal import Decimal
import pytest
from app.core.tax_utils import calculate_tax, nps_tax_benefit


def test_tax_zero_income():
    assert calculate_tax(Decimal("0")) == Decimal("0")


def test_tax_below_7l():
    # Below 7L — 0% tax
    assert calculate_tax(Decimal("600000")) == Decimal("0")


def test_tax_exactly_7l():
    assert calculate_tax(Decimal("700000")) == Decimal("0")


def test_tax_8l():
    # 7L at 0% + 1L at 10% = 10,000
    assert calculate_tax(Decimal("800000")) == Decimal("10000.00")


def test_tax_11l():
    # 7L @0% + 3L @10% + 1L @15% = 30000 + 15000 = 45000
    assert calculate_tax(Decimal("1100000")) == Decimal("45000.00")


def test_tax_13l():
    # 7L@0% + 3L@10% + 2L@15% + 1L@20% = 0+30000+30000+20000 = 80000
    assert calculate_tax(Decimal("1300000")) == Decimal("80000.00")


def test_tax_above_15l():
    # 7L@0% + 3L@10% + 2L@15% + 3L@20% + 2L@30% = 0+30000+30000+60000+60000=180000
    assert calculate_tax(Decimal("1700000")) == Decimal("180000.00")


def test_nps_tax_benefit_capped_at_2l():
    # Invested 5L, income 50L — capped at 2L
    benefit = nps_tax_benefit(Decimal("500000"), Decimal("5000000"))
    # tax(50L) - tax(48L), top slab so benefit = 2L * 0.30 = 60000
    assert benefit == Decimal("60000.00")


def test_nps_tax_benefit_capped_at_10_percent():
    # Invested 1L, income 5L (10% = 50000) — deduction limited to 50000
    benefit = nps_tax_benefit(Decimal("100000"), Decimal("500000"))
    # income 5L is under 7L so tax = 0 in both cases
    assert benefit == Decimal("0.00")


def test_nps_tax_benefit_normal():
    # Invested 50000, income 10L (10% = 1L, so deduction = 50000)
    # tax(10L) = 0+30000 = 30000; tax(9.5L) = 0+25000 = 25000; benefit = 5000
    benefit = nps_tax_benefit(Decimal("50000"), Decimal("1000000"))
    assert benefit == Decimal("5000.00")
