from decimal import Decimal
import pytest
from app.core.math_utils import ceiling, remnant


def test_ceiling_regular():
    assert ceiling(Decimal("1519")) == Decimal("1600")


def test_ceiling_already_multiple():
    assert ceiling(Decimal("1500")) == Decimal("1500")


def test_ceiling_just_above_multiple():
    assert ceiling(Decimal("1501")) == Decimal("1600")


def test_remnant_regular():
    assert remnant(Decimal("1519")) == Decimal("81")


def test_remnant_multiple_of_100():
    assert remnant(Decimal("2000")) == Decimal("0")


def test_remnant_just_above():
    assert remnant(Decimal("100.01")) == Decimal("99.99")


def test_ceiling_zero():
    assert ceiling(Decimal("0")) == Decimal("0")


def test_remnant_zero():
    assert remnant(Decimal("0")) == Decimal("0")


def test_ceiling_99():
    assert ceiling(Decimal("99")) == Decimal("100")


def test_remnant_99():
    assert remnant(Decimal("99")) == Decimal("1")
