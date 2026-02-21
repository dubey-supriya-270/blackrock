import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_parse_flat_list():
    """Parse accepts a flat list of {date, amount}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "2023-10-12 20:15:30", "amount": 250},
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-07-01 21:59:00", "amount": 620},
        ])
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # 250 → ceiling 300, remanent 50
    assert data[0]["ceiling"] == 300.0
    assert data[0]["remanent"] == 50.0
    # 375 → ceiling 400, remanent 25
    assert data[1]["ceiling"] == 400.0
    assert data[1]["remanent"] == 25.0
    # 620 → ceiling 700, remanent 80
    assert data[2]["ceiling"] == 700.0
    assert data[2]["remanent"] == 80.0


@pytest.mark.asyncio
async def test_parse_multiple_of_100():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "2023-01-01 10:00:00", "amount": 2000},
        ])
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["ceiling"] == 2000.0
    assert data[0]["remanent"] == 0.0


@pytest.mark.asyncio
async def test_parse_invalid_date_format():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:parse", json=[
            {"date": "15-01-2023", "amount": 1000}
        ])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_validator_negative_amount():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": "50000",
            "transactions": [
                {"date": "2023-01-15 10:30:00", "amount": 2000,  "ceiling": 2000, "remanent": 0},
                {"date": "2023-07-10 09:15:00", "amount": -250,  "ceiling": 0,    "remanent": 0},
            ]
        })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["valid"]) == 1
    assert len(data["invalid"]) == 1
    assert "Negative" in data["invalid"][0]["error"]


@pytest.mark.asyncio
async def test_validator_duplicate_date():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:validator", json={
            "wage": "50000",
            "transactions": [
                {"date": "2023-01-15 10:30:00", "amount": 2000, "ceiling": 2000, "remanent": 0},
                {"date": "2023-01-15 10:30:00", "amount": 3500, "ceiling": 3600, "remanent": 100},
            ]
        })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["valid"]) == 1
    assert "Duplicate" in data["invalid"][0]["error"]


@pytest.mark.asyncio
async def test_filter_compact_format():
    """Full compact format: q overrides, p adds, k flags, auto-computes ceiling/remanent."""
    payload = {
        "age": 29,
        "wage": 50000,
        "inflation": 5.5,
        "q": [{"fixed": 0, "start": "2023-07-01 00:00:00", "end": "2023-07-31 23:59:59"}],
        "p": [{"extra": 25, "start": "2023-10-01 00:00:00", "end": "2023-12-31 19:59:59"}],
        "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
        "transactions": [
            {"date": "2023-02-28 15:49:20", "amount": 375},   # remanent=25, no q/p
            {"date": "2023-07-01 21:59:00", "amount": 620},   # remanent=80→q→0
            {"date": "2023-10-12 20:15:30", "amount": 250},   # remanent=50+25(p)=75
            {"date": "2023-12-17 08:09:45", "amount": 480},   # remanent=20+25(p)=45
            {"date": "2023-12-17 08:09:45", "amount": -10},   # duplicate + negative → invalid
        ]
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/transactions:filter", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    valid = data["valid"]
    invalid = data["invalid"]

    assert len(valid) == 4
    # Last transaction is BOTH negative AND duplicate → 2 invalid entries
    assert len(invalid) == 2
    invalid_errors = {e["error"] for e in invalid}
    assert "Negative amounts are not allowed" in invalid_errors
    assert "Duplicate transaction date" in invalid_errors

    assert valid[0]["remanent"] == 25.0
    assert valid[0]["in_q_period"] is False
    assert valid[0]["in_p_period"] is False
    assert valid[0]["in_k_period"] is True

    # 2023-07-01: q overrides to 0
    assert valid[1]["remanent"] == 0.0
    assert valid[1]["in_q_period"] is True

    # 2023-10-12: remanent=50 + p(25) = 75
    assert valid[2]["remanent"] == 75.0
    assert valid[2]["in_p_period"] is True

    # last txn invalid (duplicate + or negative)
    assert "Duplicate" in invalid[0]["error"] or "Negative" in invalid[0]["error"]


@pytest.mark.asyncio
async def test_nps_returns_compact():
    payload = {
        "age": 29, "wage": 50000, "inflation": 5.5,
        "q": [], "p": [],
        "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
        "transactions": [
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-07-01 21:59:00", "amount": 620},
        ]
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/returns:nps", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["savings_by_dates"]) == 1
    s = data["savings_by_dates"][0]
    assert isinstance(s["profit"], float)          # inflation-adjusted real gain
    assert float(s["amount"]) >= 0
    assert s["tax_benefit"] is not None
    assert "start" in s and "end" in s


@pytest.mark.asyncio
async def test_index_returns_no_tax_compact():
    payload = {
        "age": 29, "wage": 50000, "inflation": 5.5,
        "q": [], "p": [],
        "k": [{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
        "transactions": [{"date": "2023-07-01 21:59:00", "amount": 620}]
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/blackrock/challenge/v1/returns:index", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    s = data["savings_by_dates"][0]
    assert s["tax_benefit"] is None


@pytest.mark.asyncio
async def test_performance():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/blackrock/challenge/v1/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "time_ms" in data and "memory_mb" in data and "threads" in data
