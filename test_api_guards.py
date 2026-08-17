"""API-level tests for the T3 input-guard hardening in app/main.py.

Covers, against the live FastAPI app object (rule backend, no key needed):
  * /api/reply rejects unknown / missing / non-string lead_id (404) BEFORE use
  * /api/reply rejects empty, non-string, and oversize messages (400)
  * /api/call rejects invalid AU mobiles (400), accepts the demo mask & real AU numbers
  * /api/call rejects oversize first messages (400)
  * /api/call + /api/reply happy path still works (lead created, qualifies, hands off)
  * malformed JSON body -> 400
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# The /api/call + /api/reply routes carry a slowapi rate limit (read from env
# at import). Raise it so rapid-fire TestClient calls don't trip 429 and mask
# the input-guard assertions below.
os.environ["RATE_LIMIT_CALL"] = "10000/minute"
os.environ["RATE_LIMIT_REPLY"] = "10000/minute"

from fastapi.testclient import TestClient
from app.main import app, MAX_MESSAGE_CHARS, DEFAULT_CUSTOMER_PHONE

client = TestClient(app)

_results = []
def check(name, cond):
    _results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)

# --- /api/reply: lead_id validation BEFORE use ---------------------------------
check("reply missing lead_id -> 404", client.post("/api/reply", json={"message": "hi"}).status_code == 404)
check("reply non-string lead_id -> 404",
      client.post("/api/reply", json={"lead_id": 12345, "message": "hi"}).status_code == 404)
check("reply unknown lead_id -> 404",
      client.post("/api/reply", json={"lead_id": "nope", "message": "hi"}).status_code == 404)

# --- /api/reply: message validation --------------------------------------------
r = client.post("/api/call", json={})
lid = r.json()["lead_id"]
check("call default mask accepted", r.status_code == 200 and r.json()["lead_id"])

check("reply empty message -> 400",
      client.post("/api/reply", json={"lead_id": lid, "message": "   "}).status_code == 400)
check("reply non-string message -> 400",
      client.post("/api/reply", json={"lead_id": lid, "message": 42}).status_code == 400)
check("reply oversize message -> 400",
      client.post("/api/reply", json={"lead_id": lid, "message": "x" * (MAX_MESSAGE_CHARS + 1)}).status_code == 400)
check("reply boundary-size message accepted",
      client.post("/api/reply", json={"lead_id": lid, "message": "y" * MAX_MESSAGE_CHARS}).status_code == 200)
check("reply happy path (valid) works",
      client.post("/api/reply", json={"lead_id": lid, "message": "im in new farm"}).status_code == 200)

# --- /api/call: mobile validation ----------------------------------------------
check("call missing customer_phone defaults to mask (accepted)",
      client.post("/api/call", json={"message": "hi"}).status_code == 200)
check("call explicit demo mask accepted",
      client.post("/api/call", json={"customer_phone": DEFAULT_CUSTOMER_PHONE}).status_code == 200)
check("call valid AU mobile local accepted",
      client.post("/api/call", json={"customer_phone": "0412345678"}).status_code == 200)
check("call valid AU mobile intl (+61) accepted",
      client.post("/api/call", json={"customer_phone": "+61412345678"}).status_code == 200)
check("call invalid short mobile -> 400",
      client.post("/api/call", json={"customer_phone": "04123"}).status_code == 400)
check("call invalid landline (07...) -> 400",
      client.post("/api/call", json={"customer_phone": "0731234567"}).status_code == 400)
check("call other masked string (+614****1111) -> 400",
      client.post("/api/call", json={"customer_phone": "+614****1111"}).status_code == 400)
check("call exact demo mask accepted",
      client.post("/api/call", json={"customer_phone": "+614****0000"}).status_code == 200)
check("call non-string mobile -> 400",
      client.post("/api/call", json={"customer_phone": 123}).status_code == 400)

# --- /api/call: message validation ---------------------------------------------
check("call non-string message -> 400",
      client.post("/api/call", json={"message": ["boom"]}).status_code == 400)
check("call oversize message -> 400",
      client.post("/api/call", json={"message": "z" * (MAX_MESSAGE_CHARS + 1)}).status_code == 400)

# --- malformed JSON body -------------------------------------------------------
r = client.post("/api/call", content="{not json", headers={"Content-Type": "application/json"})
check("call malformed JSON -> 400", r.status_code == 400)

# --- full happy path: qualify + handoff still works ----------------------------
r = client.post("/api/call", json={"customer_phone": "0412345678"})
lid = r.json()["lead_id"]
for m in ["im in sunnybank hills", "burst pipe", "urgent tonight",
          "my name is jane, mobile 0412987654"]:
    resp = client.post("/api/reply", json={"lead_id": lid, "message": m})
    check(f"reply flow turn ({m[:20]}...) works", resp.status_code == 200)
qual = client.get("/api/health").status_code == 200
check("health endpoint ok", qual)

# health carries version + admin-token state for deploy verification
_h = client.get("/api/health").json()
check("health reports version field", isinstance(_h.get("version"), str))
check("health reports admin_token_configured (bool)", isinstance(_h.get("admin_token_configured"), bool))

failed = [n for n, ok in _results if not ok]
print("\n%d/%d checks passed" % (len(_results) - len(failed), len(_results)))
if failed:
    print("FAILED:", failed)
    sys.exit(1)
print("ALL OK")