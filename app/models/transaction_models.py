from __future__ import annotations
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator, field_serializer
from datetime import datetime

DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]


def _validate_date(v: str) -> str:
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(v, fmt)
            return v
        except ValueError:
            continue
    raise ValueError(f"Date must be YYYY-MM-DD HH:mm:ss or YYYY-MM-DD, got: {v!r}")


class Expense(BaseModel):
    date: str
    amount: Decimal

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        return _validate_date(v)


class Transaction(BaseModel):
    date: str
    amount: Decimal
    ceiling: Decimal
    remanent: Decimal

    @field_serializer("amount", "ceiling", "remanent")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class ValidatorRequest(BaseModel):
    wage: Decimal
    transactions: list[Transaction]


class InvalidTransaction(BaseModel):
    transaction: Transaction
    error: str


class ValidatorResponse(BaseModel):
    valid: list[Transaction]
    invalid: list[InvalidTransaction]
