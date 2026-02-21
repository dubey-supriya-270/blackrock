"""
Math utilities — optimized with NumPy for batch processing.

Layer 3 optimization: vectorize ceiling/remanent across entire
transaction arrays in one C-level operation instead of Python loops.
"""
from decimal import Decimal
import numpy as np


def ceiling(amount: Decimal) -> Decimal:
    """Single-value ceiling (next multiple of 100)."""
    amount = Decimal(str(amount))
    if amount % 100 == 0:
        return amount
    return (amount // 100 + 1) * 100


def remnant(amount: Decimal) -> Decimal:
    """Single-value remnant."""
    amount = Decimal(str(amount))
    return ceiling(amount) - amount


# ── Batch (NumPy) versions ────────────────────────────────────────────────────

def batch_ceiling(amounts: list[float]) -> np.ndarray:
    """Vectorized ceiling for a list of amounts — O(n) single C call."""
    arr = np.array(amounts, dtype=np.float64)
    multiples = np.where(arr % 100 == 0, arr, np.ceil(arr / 100) * 100)
    return multiples


def batch_remnant(amounts: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized ceiling and remanent for a list of amounts.
    Returns (ceilings, remanents) as numpy arrays.
    """
    arr = np.array(amounts, dtype=np.float64)
    ceilings = np.where(arr % 100 == 0, arr, np.ceil(arr / 100) * 100)
    remanents = ceilings - arr
    return ceilings, remanents
