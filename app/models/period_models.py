from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, Field
import uuid


class QPeriod(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: str
    end: str
    fixed: Decimal          # fixed amount to override remanent


class PPeriod(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: str
    end: str
    extra: Decimal          # extra amount to add to remanent


class KPeriod(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: str
    end: str
