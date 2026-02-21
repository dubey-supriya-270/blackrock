from decimal import Decimal


# Tax slabs (simplified new regime)
TAX_SLABS = [
    (Decimal("700000"),  Decimal("0.00")),
    (Decimal("1000000"), Decimal("0.10")),
    (Decimal("1200000"), Decimal("0.15")),
    (Decimal("1500000"), Decimal("0.20")),
    (None,               Decimal("0.30")),
]


def calculate_tax(income: Decimal) -> Decimal:
    """Calculate tax based on simplified slab rates."""
    income = Decimal(str(income))
    if income <= 0:
        return Decimal("0")

    tax = Decimal("0")
    previous_limit = Decimal("0")

    for limit, rate in TAX_SLABS:
        if limit is None:
            # Top slab — tax on the remaining income
            taxable = income - previous_limit
            tax += taxable * rate
            break
        if income <= limit:
            taxable = income - previous_limit
            tax += taxable * rate
            break
        else:
            taxable = limit - previous_limit
            tax += taxable * rate
            previous_limit = limit

    return tax.quantize(Decimal("0.01"))


def nps_tax_benefit(invested: Decimal, annual_income: Decimal) -> Decimal:
    """Compute NPS tax benefit.

    Deduction = min(invested, 10% of annual income, ₹2,00,000)
    Benefit   = tax(income) - tax(income - deduction)
    """
    invested = Decimal(str(invested))
    annual_income = Decimal(str(annual_income))

    max_deduction = Decimal("200000")
    ten_percent = annual_income * Decimal("0.10")
    deduction = min(invested, ten_percent, max_deduction)

    tax_without = calculate_tax(annual_income)
    tax_with = calculate_tax(annual_income - deduction)

    benefit = tax_without - tax_with
    return benefit.quantize(Decimal("0.01"))
