"""Functional test for /api/call and /api/reply rate limiting (T2).

Uses the rule backend (no OPENROUTER_API_KEY) so it's deterministic and
offline. HTTP requests come from the same 127.0.0.1 test client, so slowapi
counts them all as one client IP.

A reply lead is seeded once at import time (fresh rate budget) so the /api/call
and /api/reply tests don't share the same per-IP call budget.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, _CALL_LIMIT, _REPLY_LIMIT  # noqa: E402

client = TestClient(app)

# Parse the "N/minute" limit strings into the integer count.
def parse(limit: str) -> int:
    return int(limit.split("/", 1)[0].strip())


def _new_lead() -> str:
    """Create a lead via /api/call and return its id (1 call against fresh budget)."""
    r = client.post(
        "/api/call", json={"customer_phone": "0412345678", "message": "leaking"}
    )
    assert r.status_code == 200, r.text
    return r.json()["lead_id"]


# Seed reply lead once before hammering /api/call below.
REPLY_LEAD_ID = _new_lead()


def test_rate_limit_call():
    n = parse(_CALL_LIMIT)
    assert n >= 1
    last_status = None
    for _ in range(n + 3):
        r = client.post(
            "/api/call",
            json={"customer_phone": "0412345678", "message": "water heater leaking"},
        )
        last_status = r.status_code
        if r.status_code == 429:
            break
    assert last_status == 429, f"expected 429 after ~{n} calls, got {last_status}"


def test_rate_limit_reply():
    n = parse(_REPLY_LIMIT)
    assert n >= 1
    last_status = None
    for _ in range(n + 3):
        r = client.post(
            "/api/reply", json={"lead_id": REPLY_LEAD_ID, "message": "suburb ashgrove"}
        )
        last_status = r.status_code
        if r.status_code == 429:
            break
    assert last_status == 429, f"expected 429 after ~{n} replies, got {last_status}"


def test_health_not_rate_limited():
    """Non-LLM endpoints must not be rate limited."""
    for _ in range(60):
        assert client.get("/api/health").status_code == 200


if __name__ == "__main__":
    print("CALL_LIMIT =", _CALL_LIMIT, "REPLY_LIMIT =", _REPLY_LIMIT)
    test_rate_limit_call()
    print("PASS /api/call rate limit")
    test_rate_limit_reply()
    print("PASS /api/reply rate limit")
    test_health_not_rate_limited()
    print("PASS non-limited endpoints unaffected")
    print("ALL RATE-LIMIT TESTS PASSED")