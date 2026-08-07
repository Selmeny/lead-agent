"""Deterministic tests for the agent brain (rule backend — no LLM needed)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app.agent import Agent, RuleBackend, Lead, BUSINESS_FACTS

def run_flow(messages, business="plumbright"):
    agent = Agent(RuleBackend())
    lead = Lead(id="test1", customer_phone="+61400000000", first_message=messages[0])
    replies = []
    lead.add("user", messages[0])
    replies.append(agent.initial_textback(lead))
    for m in messages[1:]:
        lead.add("user", m)
        replies.append(agent.respond(lead, m))
    return lead, replies

def test_full_flow():
    msgs = [
        "hi my water heater is leaking and water is everywhere, are you open?",
        "im in new farm",
        "the hot water tank is leaking",
        "needs fixing tonight, its flooding",
        "my name is maria herrera and mobile 0412345678",
    ]
    lead, replies = run_flow(msgs)
    assert lead.suburb == "New Farm", lead.suburb
    assert lead.issue is not None and any(
        kw in lead.issue.lower() for kw in ("hot water", "water heater", "tank", "leak")
    ), lead.issue
    assert "tonight" in (lead.urgency or "").lower(), lead.urgency
    assert lead.customer_name == "Maria", lead.customer_name
    assert lead.customer_mobile == "0412345678", lead.customer_mobile
    assert lead.is_qualified(), "lead should be qualified"
    assert lead.status == "qualified", lead.status
    print("PASS full_flow, summary:", lead.qualified_summary.replace("\n", " | "))

    # handoff message correctness (main.py builds this)
    handoff = lead.qualified_summary + (
        "\n• How handled: emergency after-hours → owner to call back"
    )
    assert "NEW LEAD" in handoff
    assert "Maria" in handoff and "New Farm" in handoff
    print("PASS handoff_sms contains key fields")

def test_out_of_order_fields():
    # customer blurts everything up-front
    lead, replies = run_flow([
        "hi room, we have a burst pipe in kelvin grove, my name is john smith, mobile 0412345678, its an emergency now!!",
    ])
    assert lead.suburb == "Kelvin Grove", lead.suburb
    assert lead.is_qualified(), "should qualify from single message"
    print("PASS all-in-one qualifies:", lead.qualified_summary.replace("\n", " | "))

def test_no_qualification_yet():
    lead, replies = run_flow(["my tap is dripping"])
    assert not lead.is_qualified()
    assert lead.issue and "tap" in lead.issue.lower()
    print("PASS not qualified until all fields present; issue extracted:", lead.issue)

if __name__ == "__main__":
    test_full_flow()
    test_out_of_order_fields()
    test_no_qualification_yet()
    print("\nAll deterministic agent tests PASSED")
