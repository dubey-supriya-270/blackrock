# BlackRock Retirement Micro-Savings API

Production-grade REST API for automated retirement savings via expense-based micro-investments. Built with Python 3.12 + FastAPI.

---

## Quick Start

### With Docker (recommended)

```bash
docker compose up --build
```

| URL | Description |
|---|---|
| `http://localhost:5477/docs` | Swagger UI (interactive) |
| `http://localhost:5477/redoc` | ReDoc |
| `http://localhost:5477/health` | Liveness probe |
| `http://localhost:5477/ready` | Readiness probe |
| `http://localhost/docs` | Via Nginx (port 80) |

### Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
```

### Run Tests

```bash
pytest tests/ -v    # 38 tests — unit + integration
```

---

## API Reference

Base path: `/blackrock/challenge/v1`

### `POST /transactions:parse`

Accepts a **flat list** of raw expenses. Returns each enriched with `ceiling` and `remanent`.

```json
[
  {"date": "2023-02-28 15:49:20", "amount": 375},
  {"date": "2023-07-15 10:30:00", "amount": 620}
]
```

**Response**
```json
[
  {"date": "2023-02-28 15:49:20", "amount": 375.0, "ceiling": 400.0, "remanent": 25.0},
  {"date": "2023-07-15 10:30:00", "amount": 620.0, "ceiling": 700.0, "remanent": 80.0}
]
```

**Math**: `ceiling = next multiple of 100 ≥ amount`, `remanent = ceiling − amount`

---

### `POST /transactions:validator`

Validates enriched transactions — detects negatives and duplicate dates.

```json
{
  "wage": 50000,
  "transactions": [
    {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2000, "remanent": 0},
    {"date": "2023-07-10 09:15:00", "amount": -250, "ceiling": 300,  "remanent": 50}
  ]
}
```

**Response**: `{"valid": [...], "invalid": [{"transaction": {...}, "error": "Negative amounts are not allowed"}]}`

---

### `POST /transactions:filter`

Applies q/p/k period rules on **raw transactions** (ceiling/remanent auto-computed). Returns boolean flags per transaction.

```json
{
  "age": 29, "wage": 50000, "inflation": 5.5,
  "q": [{"fixed": 0,  "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
  "p": [{"extra": 25, "start": "2023-10-01 00:00:00", "end": "2023-12-31 19:59:59"}],
  "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
  "transactions": [
    {"date": "2023-02-28 15:49:20", "amount": 375},
    {"date": "2023-07-01 21:59:00", "amount": 620},
    {"date": "2023-12-17 08:09:45", "amount": -10}
  ]
}
```

**Period Rules**:

| Period | Field | Behaviour |
|---|---|---|
| **q** | `fixed` | Replaces `remanent` with fixed amount. Latest-start wins on overlap. |
| **p** | `extra` | Adds extra amount to `remanent`. All matching p periods are cumulative. |
| **k** | _(none)_ | Groups transactions for returns projection. Transaction can belong to multiple k periods. |

> Invalid dates like `Nov 31` are automatically clamped to the last valid day of the month.

**Response**:
```json
{
  "valid": [
    {"date": "...", "amount": 375.0, "ceiling": 400.0, "remanent": 25.0,
     "in_q_period": false, "in_p_period": false, "in_k_period": true}
  ],
  "invalid": [
    {"date": "...", "amount": -10.0, "error": "Negative amounts are not allowed"}
  ]
}
```

---

### `POST /returns:nps` and `POST /returns:index`

Projects retirement savings. **Same payload format as `/transactions:filter`.**

| Vehicle | Rate | Tax Benefit |
|---|---|---|
| NPS | 7.11% p.a. | Section 80CCD — up to ₹2,00,000 or 10% of annual income |
| Index Fund | 14.49% p.a. | `null` (no deduction scheme) |

> Use `wage ≥ 58334` (monthly) to see non-zero `tax_benefit` — annual income must exceed ₹7L tax threshold.

**Response**:
```json
{
  "total_transaction_amount": 1725.0,
  "total_ceiling": 1900.0,
  "savings_by_dates": [
    {
      "start": "2023-01-01 00:00:00",
      "end":   "2023-12-31 23:59:59",
      "amount": 145.0,
      "tax_benefit": 0.0,
      "profit": 86.89
    }
  ]
}
```

**Formulas**:
- `future_value = principal × (1 + rate)^t` where `t = 60 − age`
- `real_value = future_value / (1 + inflation/100)^t`
- `profit = real_value − principal` (inflation-adjusted net gain)
- `tax_benefit = tax(income) − tax(income − NPS_deduction)`

---

### `GET /performance`

```json
{"time_ms": 0.3, "memory_mb": 54.2, "threads": 4}
```

### `GET /health` · `GET /ready`

Liveness and readiness probes for Kubernetes / Docker healthchecks.

---

## Architecture

### Project Structure

```
finance/
├── app/
│   ├── main.py              # FastAPI app, CORS, middleware, exception handler
│   ├── config.py            # Pydantic Settings (all env vars centralised)
│   ├── logging_config.py    # Structured JSON logging
│   ├── routers/
│   │   ├── transactions.py  # :parse, :validator, :filter
│   │   ├── returns.py       # :nps, :index
│   │   └── performance.py   # /performance
│   ├── core/
│   │   ├── math_utils.py    # ceiling, remnant + NumPy batch functions
│   │   ├── period_utils.py  # IntervalTree q/p/k matching
│   │   ├── tax_utils.py     # Progressive tax slabs + NPS benefit
│   │   ├── finance_utils.py # Compound interest, real return, years calc
│   │   └── cache.py         # L1 (TTLCache) + L2 (Redis) two-level cache
│   └── models/
│       ├── transaction_models.py
│       ├── period_models.py
│       └── return_models.py
├── tests/                   # 38 tests (unit + integration)
├── Dockerfile               # Multi-stage build
├── compose.yaml             # Nginx + API + Redis
├── nginx.conf               # L7 load balancer + micro-cache
└── requirements.txt
```

### Performance Design

| Layer | Technique | Benefit |
|---|---|---|
| **L1 Cache** | In-process `TTLCache` (~50ns hit) | Zero network for hot requests |
| **L2 Cache** | Redis async (~0.3ms hit) + fire-and-forget writes | Survives restarts |
| **Period matching** | `IntervalTree` → O(log n) | vs O(n×m) nested loops |
| **Batch math** | NumPy `batch_remnant` (C-level) | All transactions in one call |
| **HTTP server** | `uvloop` + `httptools` | 2–4× faster than CPython defaults |
| **Workers** | `2 × CPU + 1` (16 on 8-core) | Full core utilisation |
| **OS tuning** | `somaxconn=65535`, `tcp_tw_reuse`, keepalive | Kernel-level throughput |

### Production Features

- ✅ Structured JSON logs (ELK / Grafana Loki compatible)
- ✅ `X-Request-ID` header on every response (traceable)
- ✅ Global exception handler — no stack traces leaked to clients
- ✅ CORS middleware
- ✅ `/health` (liveness) + `/ready` (readiness, checks Redis)
- ✅ Graceful fallback — works without Redis (reduced performance)
- ✅ Multi-stage Docker build (smaller image, no build tools in runtime)
- ✅ `.gitignore` — secrets excluded

---

## Tax Slabs (New Regime)

| Income | Rate |
|---|---|
| Up to ₹7,00,000 | 0% |
| ₹7,00,001 – ₹10,00,000 | 10% |
| ₹10,00,001 – ₹12,00,000 | 15% |
| ₹12,00,001 – ₹15,00,000 | 20% |
| Above ₹15,00,000 | 30% |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `CACHE_TTL_SECONDS` | `60` | Cache TTL for both L1 and L2 |
| `L1_CACHE_MAXSIZE` | `4096` | Max entries in in-process cache |
| `REDIS_POOL_SIZE` | `50` | Redis connection pool size |
| `DEBUG` | `false` | Enable debug logging |
