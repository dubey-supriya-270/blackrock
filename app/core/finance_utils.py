from decimal import Decimal


NPS_RATE = Decimal("0.0711")
INDEX_RATE = Decimal("0.1449")
RETIREMENT_AGE = 60


def compound_interest(principal: Decimal, rate: Decimal, years: int) -> Decimal:
    """A = P * (1 + r)^t  (n=1, compounded annually)."""
    if years <= 0:
        return principal
    principal = Decimal(str(principal))
    return principal * (1 + rate) ** years


def real_return(future_value: Decimal, inflation: Decimal, years: int) -> Decimal:
    """A_real = A / (1 + inflation)^t"""
    if years <= 0:
        return future_value
    future_value = Decimal(str(future_value))
    inflation = Decimal(str(inflation))
    return future_value / (1 + inflation) ** years


def years_to_retirement(current_age: int) -> int:
    """Years remaining until retirement age (60)."""
    return max(0, RETIREMENT_AGE - current_age)
