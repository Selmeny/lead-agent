"""Comprehensive deterministic tests for the lead-agent brain (rule backend).

Covers the regression that produced the "stupid" behaviour seen in the demo:
the agent re-asked "which suburb are you in?" AFTER the customer already said
"Sunnybank Hills". Root causes: (A) suburb whitelist missed Sunnybank (southside)
so the field was never captured; (B) the LLM silently fell back to the rule
backend, which blindly asked the next "missing" field.

These tests are deterministic (no LLM) and assert the *behaviour contract*:
- extracted fields are correct (incl. southside suburbs)
- the agent NEVER re-asks for a field the customer already provided
- exactly ONE question per turn
- flow qualifies and hands off correctly
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.agent import Agent, RuleBackend, Lead

def run_flow(messages):
    agent = Agent(RuleBackend())
    lead = Lead(id="t", customer_phone="+614****0000", first_message=messages[0])
    lead.add("user", messages[0])
    replies = [agent.initial_textback(lead)]
    for m in messages[1:]:
        lead.add("user", m)
        replies.append(agent.respond(lead, m))
    return lead, replies

# Every rule reply is exactly one question — count '?' (allow one).
def assert_one_question(reply, label):
    q = reply.count("?")
    assert q >= 0
    # A single genuine question: exactly one '?'. Multiple '?' = multi-question spam.
    assert q == 1, f"{label}: expected exactly one '?' got {q}: {reply!r}"


def test_screenshot_repro_sunnybank_not_requestioned():
    """REGRESSION: the exact conversation that looked 'stupid'."""
    msgs = [
        "hi my water heater is leaking and water is going everywhere. are you open?",
        "Sunnybank hills",
        "Burst pipe",
        "it is urgent tonight, my name is maria, mobile 0412345678",
    ]
    lead, replies = run_flow(msgs)
    # Bug A: southside suburb must be captured.
    assert lead.suburb == "Sunnybank Hills", f"suburb not captured: {lead.suburb!r}"
    # The reply immediately after "Sunnybank hills" must NOT re-ask suburb.
    assert "suburb" not in replies[1].lower(), replies[1]
    assert lead.issue, "issue should be extracted"
    assert lead.is_qualified(), "lead should qualify"
    print("PASS screenshot repro: suburb captured, never re-asked, qualified ->",
          lead.qualified_summary.replace("\n", " | "))

def test_no_reask_after_field_provided():
    """The agent must never ask again for something already known."""
    msgs = [
        "my water heater is leaking, are you open?",
        "im in ashgrove",
        "my name is bob",
    ]
    lead, replies = run_flow(msgs)
    assert lead.suburb == "Ashgrove", lead.suburb
    assert lead.customer_name == "Bob", lead.customer_name
    # Turn 2 reply is about the issue (suburb already known -> never re-ask suburb)
    assert "suburb" not in replies[1].lower(), replies[1]
    # Turn 3 reply must not re-ask name or suburb
    low3 = replies[2].lower()
    assert "name" not in low3 and "suburb" not in low3, replies[2]
    print("PASS no re-asking: suburb+name captured and not re-asked")

def test_single_question_per_turn():
    """Every rule reply contains exactly one question."""
    msgs = [
        "my tap is leaking, are you open?",
        "im in wilston",
        "its a burst pipe",
        "urgent today",
        "this is tom, 0412987654",
    ]
    _, replies = run_flow(msgs)
    for i, r in enumerate(replies):
        # While still qualifying, exactly one question per reply. The FINAL
        # booking confirmation must ask zero questions.
        expected = 0 if i == len(replies) - 1 else 1
        assert r.count("?") == expected, f"reply[{i}] expected {expected} '?' got {r.count('?')}: {r!r}"
    print(f"PASS single-question-per-turn for {len(replies)} turns")

def test_out_of_order_qualify():
    lead, replies = run_flow([
        "hi we have a burst pipe in kelvin grove, my name is john smith, mobile 0412345678, its an emergency now!!",
    ])
    assert lead.suburb == "Kelvin Grove", lead.suburb
    assert lead.is_qualified()
    print("PASS out-of-order qualify")

def test_southside_suburbs_known():
    """Southside suburbs must be recognised (regression: Sunnybank was missing)."""
    for s in ["Sunnybank", "Sunnybank Hills", "Coorparoo", "Mount Gravatt",
              "Woolloongabba", "Annerley", "Holland Park"]:
        lead, _ = run_flow([f"im in {s}"])
        assert lead.suburb == s.title(), f"suburb {s!r} not recognised -> {lead.suburb!r}"
    print("PASS southside suburbs recognised")

def test_no_reask_and_final_handoff_booking():
    """Once qualified, reply is a booking confirmation, not another question."""
    msgs = ["pipe burst my place",
            "im in new farm",
            "burst pipe",
            "urgent tonight",
            "my name is anna, mobile 0400111222"]
    lead, replies = run_flow(msgs)
    assert lead.is_qualified()
    last = replies[-1]
    assert "book" in last.lower(), last
    assert "?" not in last, last
    print("PASS qualified -> booking confirmation, no dangling question")

if __name__ == "__main__":
    test_screenshot_repro_sunnybank_not_requestioned()
    test_no_reask_after_field_provided()
    test_single_question_per_turn()
    test_out_of_order_qualify()
    test_southside_suburbs_known()
    test_no_reask_and_final_handoff_booking()
    print("\nAll comprehensive agent tests PASSED")
