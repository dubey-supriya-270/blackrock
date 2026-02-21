from __future__ import annotations
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_serializer
from app.models.period_models import QPeriod, PPeriod, KPeriod
from app.models.transaction_models import Expense


class FilteredTransaction(BaseModel):
    date: str
    amount: Decimal
    ceiling: Decimal
    remanent: Decimal
    in_q_period: bool = False
    in_p_period: bool = False
    in_k_period: bool = False

    @field_serializer("amount", "ceiling", "remanent")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class InvalidFilteredTransaction(BaseModel):
    date: str
    amount: Decimal
    error: str

    @field_serializer("amount")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)


class FilterRequest(BaseModel):
    age: int = 30
    wage: Decimal
    inflation: Decimal = Decimal("0.06")
    q: list[QPeriod] = []
    p: list[PPeriod] = []
    k: list[KPeriod] = []
    transactions: list[Expense]


class FilterResponse(BaseModel):
    valid: list[FilteredTransaction]
    invalid: list[InvalidFilteredTransaction]


class SavingsByDate(BaseModel):
    start: str
    end: str
    amount: Decimal
    tax_benefit: Optional[Decimal] = None
    profit: Decimal

    @field_serializer("amount", "profit")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)

    @field_serializer("tax_benefit")
    def serialize_optional_decimal(self, v: Optional[Decimal]) -> Optional[float]:
        return float(v) if v is not None else None


class ReturnResponse(BaseModel):
    total_transaction_amount: Decimal
    total_ceiling: Decimal
    savings_by_dates: list[SavingsByDate]

    @field_serializer("total_transaction_amount", "total_ceiling")
    def serialize_decimal(self, v: Decimal) -> float:
        return float(v)
