from decimal import Decimal
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.models.return_models import FilterRequest, ReturnResponse, SavingsByDate
from app.core.math_utils import batch_remnant
from app.core.period_utils import apply_q_rule, apply_p_rules, _parse_date, build_q_tree, build_p_tree
from app.core.finance_utils import compound_interest, real_return, years_to_retirement, NPS_RATE, INDEX_RATE
from app.core.tax_utils import nps_tax_benefit
from app.core.cache import make_cache_key, cache_get, cache_set
import json

router = APIRouter(prefix="/blackrock/challenge/v1", tags=["Returns"])


async def _compute_returns(
    request_obj: Request,
    request: FilterRequest,
    rate: Decimal,
    include_tax: bool,
) -> ReturnResponse:
    # Cache check
    body = await request_obj.body()
    cache_suffix = "nps" if include_tax else "index"
    key = make_cache_key("POST", request_obj.url.path + cache_suffix, body)
    hit = await cache_get(key)
    if hit:
        return JSONResponse(content=json.loads(hit))

    # Pre-build IntervalTrees once — O(P log P)
    q_dicts = [qp.model_dump() for qp in request.q]
    p_dicts = [pp.model_dump() for pp in request.p]
    q_tree = build_q_tree(q_dicts)
    p_tree = build_p_tree(p_dicts)

    # NumPy batch ceiling/remanent for all transactions at once
    valid_expenses = []
    seen: set[str] = set()
    for exp in request.transactions:
        amt = Decimal(str(exp.amount))
        if amt < 0 or exp.date in seen:
            continue
        seen.add(exp.date)
        valid_expenses.append(exp)

    amounts = [float(e.amount) for e in valid_expenses]
    ceilings_arr, remanents_arr = batch_remnant(amounts) if amounts else ([], [])

    total_amount = Decimal("0")
    total_ceil = Decimal("0")
    enriched = []

    for i, expense in enumerate(valid_expenses):
        amt = Decimal(str(expense.amount))
        total_amount += amt
        total_ceil += Decimal(str(round(float(ceilings_arr[i]), 2)))
        rem_val = Decimal(str(round(float(remanents_arr[i]), 2)))

        # O(log n) IntervalTree lookups
        rem_val, _ = apply_q_rule(expense.date, rem_val, [], _q_tree=q_tree)
        rem_val, _ = apply_p_rules(expense.date, rem_val, [], _p_tree=p_tree)
        enriched.append({"date": expense.date, "remanent": rem_val})

    t = years_to_retirement(request.age)
    inflation = Decimal(str(request.inflation)) / 100 if request.inflation > 1 else Decimal(str(request.inflation))
    annual_income = request.wage * 12

    savings = []
    for kp in request.k:
        start_d = _parse_date(kp.start)
        end_d   = _parse_date(kp.end)

        principal = sum(
            row["remanent"] for row in enriched
            if start_d <= _parse_date(row["date"]) <= end_d
        ) or Decimal("0")

        fv     = compound_interest(principal, rate, t).quantize(Decimal("0.01"))
        rv     = real_return(fv, inflation, t).quantize(Decimal("0.01"))
        tax    = nps_tax_benefit(principal, annual_income) if include_tax else None
        profit = (rv - principal).quantize(Decimal("0.01"))

        savings.append(SavingsByDate(
            start=kp.start, end=kp.end,
            amount=principal.quantize(Decimal("0.01")),
            tax_benefit=tax,
            profit=profit,
        ))

    result = ReturnResponse(
        total_transaction_amount=total_amount.quantize(Decimal("0.01")),
        total_ceiling=total_ceil.quantize(Decimal("0.01")),
        savings_by_dates=savings,
    )
    await cache_set(key, json.dumps(result.model_dump(mode="json")))
    return result


@router.post("/returns:nps", response_model=ReturnResponse)
async def nps_returns(request_obj: Request, request: FilterRequest) -> ReturnResponse:
    """NPS — 7.11% annual, tax benefit included."""
    return await _compute_returns(request_obj, request, NPS_RATE, include_tax=True)


@router.post("/returns:index", response_model=ReturnResponse)
async def index_returns(request_obj: Request, request: FilterRequest) -> ReturnResponse:
    """Index Fund — 14.49% annual, no tax benefit."""
    return await _compute_returns(request_obj, request, INDEX_RATE, include_tax=False)
