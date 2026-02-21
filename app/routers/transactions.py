"""
Transaction routers — parse, validator, filter.

Production patterns applied:
  - All cache hits deserialize back to pydantic models (not raw JSONResponse)
  - IntervalTrees built once per request and reused across all transactions
  - NumPy batch_remnant vectorizes ceiling/remanent for entire array
  - Structured logging with request context
"""
import json
import logging
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Request

from app.core.cache import make_cache_key, cache_get, cache_set
from app.core.math_utils import ceiling, remnant, batch_remnant
from app.core.period_utils import (
    _parse_date, apply_q_rule, apply_p_rules,
    build_q_tree, build_p_tree,
)
from app.models.return_models import (
    FilterRequest, FilterResponse, FilteredTransaction, InvalidFilteredTransaction,
)
from app.models.transaction_models import (
    Expense, Transaction, ValidatorRequest, ValidatorResponse, InvalidTransaction,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/blackrock/challenge/v1", tags=["Transactions"])


# ── :parse ────────────────────────────────────────────────────────────────────
@router.post("/transactions:parse", response_model=List[Transaction])
async def parse_transactions(request: Request, expenses: List[Expense]) -> List[Transaction]:
    """Enrich raw expenses with ceiling and remanent.
    Input: flat list of {date, amount}.
    """
    body = await request.body()
    key = make_cache_key("POST", str(request.url.path), body)

    hit = await cache_get(key)
    if hit:
        # Always deserialize to pydantic — never return raw JSONResponse
        return [Transaction(**t) for t in json.loads(hit)]

    amounts = [float(e.amount) for e in expenses]
    ceilings_arr, remanents_arr = batch_remnant(amounts)

    result = [
        Transaction(
            date=e.date,
            amount=Decimal(str(e.amount)),
            ceiling=Decimal(str(round(ceilings_arr[i], 2))),
            remanent=Decimal(str(round(remanents_arr[i], 2))),
        )
        for i, e in enumerate(expenses)
    ]
    await cache_set(key, json.dumps([r.model_dump(mode="json") for r in result]))
    return result


# ── :validator ────────────────────────────────────────────────────────────────
@router.post("/transactions:validator", response_model=ValidatorResponse)
def validate_transactions(request: ValidatorRequest) -> ValidatorResponse:
    """Validate enriched transactions for negatives and duplicate dates."""
    valid: list[Transaction] = []
    invalid: list[InvalidTransaction] = []
    seen: set[str] = set()

    for txn in request.transactions:
        errors: list[str] = []

        if txn.amount < 0:
            errors.append("Negative amounts are not allowed")
        if txn.date in seen:
            errors.append("Duplicate transaction date")
        else:
            seen.add(txn.date)

        if errors:
            for e in errors:
                invalid.append(InvalidTransaction(transaction=txn, error=e))
        else:
            valid.append(txn)

    return ValidatorResponse(valid=valid, invalid=invalid)


# ── :filter ───────────────────────────────────────────────────────────────────
@router.post("/transactions:filter", response_model=FilterResponse)
async def filter_transactions(request: Request, payload: FilterRequest) -> FilterResponse:
    """Apply q/p/k period rules on raw transactions (auto-computes ceiling/remanent)."""
    body = await request.body()
    key = make_cache_key("POST", str(request.url.path), body)

    hit = await cache_get(key)
    if hit:
        data = json.loads(hit)
        return FilterResponse(
            valid=[FilteredTransaction(**t) for t in data["valid"]],
            invalid=[InvalidFilteredTransaction(**t) for t in data["invalid"]],
        )

    # Pre-build IntervalTrees once — O(P log P), reused for every transaction O(log P)
    q_tree = build_q_tree([qp.model_dump() for qp in payload.q])
    p_tree = build_p_tree([pp.model_dump() for pp in payload.p])

    amounts = [float(e.amount) for e in payload.transactions]
    ceilings_arr, remanents_arr = batch_remnant(amounts)

    valid: list[FilteredTransaction] = []
    invalid: list[InvalidFilteredTransaction] = []
    seen: set[str] = set()

    for i, expense in enumerate(payload.transactions):
        errors: list[str] = []

        if expense.amount < 0:
            errors.append("Negative amounts are not allowed")
        if expense.date in seen:
            errors.append("Duplicate transaction date")
        else:
            seen.add(expense.date)

        if errors:
            for e in errors:
                invalid.append(InvalidFilteredTransaction(
                    date=expense.date, amount=expense.amount, error=e,
                ))
            continue

        ceil_val = Decimal(str(round(ceilings_arr[i], 2)))
        rem_val  = Decimal(str(round(remanents_arr[i], 2)))

        rem_val, matched_q  = apply_q_rule(expense.date, rem_val, [], _q_tree=q_tree)
        rem_val, matched_ps = apply_p_rules(expense.date, rem_val, [], _p_tree=p_tree)

        txn_d = _parse_date(expense.date)
        in_k = any(
            _parse_date(kp.start) <= txn_d <= _parse_date(kp.end)
            for kp in payload.k
        )

        valid.append(FilteredTransaction(
            date=expense.date,
            amount=Decimal(str(expense.amount)),
            ceiling=ceil_val,
            remanent=rem_val,
            in_q_period=matched_q is not None,
            in_p_period=len(matched_ps) > 0,
            in_k_period=in_k,
        ))

    response = FilterResponse(valid=valid, invalid=invalid)
    await cache_set(key, json.dumps(response.model_dump(mode="json")))
    return response
