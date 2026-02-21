# BlackRock Retirement Micro-Savings API

A production-grade REST API for automated retirement savings using expense-based micro-investments. Built with Python + FastAPI.

## Features

- **Transaction Builder** — Enriches raw expenses with `ceiling` and `remanent` fields
- **Transaction Validator** — Detects negative amounts and duplicates
- **Temporal Filter** — Applies q (fixed override), p (additive), and k (grouping) period rules
- **Returns Calculator** — Projects savings via NPS (7.11%) or Index Fund (14.49%) with inflation adjustment
- **Performance Monitor** — Reports response time, memory, and thread metrics

---

## Quick Start (Docker)

```bash
# Build and run with Docker Compose
docker compose up --build

# Or build manually
docker build -t blk-hacking-ind-retirement-savings .
docker run -p 5477:5477 blk-hacking-ind-retirement-savings
```

API will be available at: **http://localhost:5477**  
Swagger UI (interactive docs): **http://localhost:5477/docs**

---

## Local Development

### Prerequisites
- Python 3.12+
- pip

### Setup

```bash
cd /home/supriya/Projects/finance

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
```

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## API Reference

All endpoints are prefixed with `/blackrock/challenge/v1`.

### `POST /transactions:parse`

Enrich raw expenses with ceiling and remanent.

**Request**
```json
{
  "expenses": [
    { "date": "2024-01-15 10:00:00", "amount": "1519" }
  ]
}
```
**Response**
```json
{
  "transactions": [
    { "date": "2024-01-15 10:00:00", "amount": "1519", "ceiling": "1600", "remanent": "81" }
  ]
}
```

---

### `POST /transactions:validator`

Validate transactions; detect negatives and duplicates.

**Request**
```json
{
  "wage": "50000",
  "transactions": [...]
}
```
**Response**
```json
{
  "valid": [...],
  "invalid": [{ "transaction": {...}, "error": "Negative amounts are not allowed" }]
}
```

---

### `POST /transactions:filter`

Apply q, p, k temporal period rules.

**Request**
```json
{
  "wage": "60000",
  "age": 30,
  "inflation": "0.06",
  "q_periods": [{ "id": "q1", "start": "2024-01-01", "end": "2024-01-31", "fixed_amount": "200" }],
  "p_periods": [{ "id": "p1", "start": "2024-01-01", "end": "2024-01-31", "extra_amount": "50" }],
  "k_periods": [{ "id": "k1", "start": "2024-01-01", "end": "2024-12-31" }],
  "transactions": [...]
}
```

**Period Rules**:
- **q period**: `remanent` is replaced by `fixed_amount`. If multiple q periods match, the one with the **latest start date** wins.
- **p period**: `extra_amount` is added to `remanent`. All matching p periods are **cumulative**.
- **k period**: Groups transactions for savings projection. A transaction can belong to **multiple k periods**.

---

### `POST /returns:nps`

Project savings using NPS (7.11% p.a., includes tax benefits).

### `POST /returns:index`

Project savings using Index Fund (14.49% p.a., no tax benefit).

**Shared Request format** (same as `/transactions:filter`):

**Response**
```json
{
  "total_transaction_amount": "1519.00",
  "total_ceiling": "1600.00",
  "k_period_returns": [{
    "k_period_id": "k1",
    "total_invested": "81.00",
    "future_value": "285.15",
    "real_value": "79.34",
    "tax_benefit": "0.00"
  }]
}
```

**Formulas**:
- Compound Interest: `A = P × (1 + r)^t` where `t = 60 - current_age`
- Real Return: `A_real = A / (1 + inflation)^t`
- NPS Deduction: `min(invested, 10% × annual_income, ₹2,00,000)`

---

### `GET /performance`

```json
{ "time_ms": 0.123, "memory_mb": 45.2, "threads": 4 }
```

---

## Investment Details

| Vehicle | Annual Rate | Tax Benefit |
|---|---|---|
| NPS | 7.11% | Up to ₹2,00,000 (10% of income) |
| Index Fund | 14.49% | None |

**Tax Slabs (Simplified)**:

| Income Range | Rate |
|---|---|
| Up to ₹7,00,000 | 0% |
| ₹7,00,001 – ₹10,00,000 | 10% |
| ₹10,00,001 – ₹12,00,000 | 15% |
| ₹12,00,001 – ₹15,00,000 | 20% |
| Above ₹15,00,000 | 30% |

---

## Project Structure

```
finance/
├── app/
│   ├── main.py              # FastAPI application
│   ├── routers/
│   │   ├── transactions.py  # :parse, :validator, :filter
│   │   ├── returns.py       # :nps, :index
│   │   └── performance.py   # /performance
│   ├── core/
│   │   ├── math_utils.py    # ceiling, remnant
│   │   ├── period_utils.py  # q/p/k period logic
│   │   ├── tax_utils.py     # tax slabs, NPS rebate
│   │   └── finance_utils.py # compound interest, inflation
│   └── models/
│       ├── transaction_models.py
│       ├── period_models.py
│       └── return_models.py
├── tests/
│   ├── test_math_utils.py
│   ├── test_tax_utils.py
│   ├── test_period_utils.py
│   └── test_endpoints.py
├── Dockerfile
├── compose.yaml
├── requirements.txt
└── README.md
```
