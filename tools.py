"""
Tool dispatcher — routes Claude tool calls to calendar_sim implementations.
"""

from calendar_sim import (
    check_availability,
    book_appointment,
    lookup_appointment,
    cancel_appointment,
)


def send_confirmation(patient_name: str, phone_number: str,
                      appointment_details: str) -> dict:
    """Mock SMS — prints to console. Replace with Twilio in Phase 3."""
    print(f"\n   📱  [MOCK SMS] -> {phone_number}")
    print(f"       Berkeley Optometry: Hi {patient_name}, your appointment is confirmed.")
    print(f"       Details: {appointment_details}\n")
    return {"success": True, "sent_to": phone_number}


def escalate_to_human(reason: str) -> dict:
    print(f"\n   🚨  [ESCALATION] Reason: {reason}\n")
    return {
        "escalated": True,
        "message": "Transferring to staff. Please hold.",
        "reason": reason,
    }


def end_call(summary: str) -> dict:
    return {"ended": True, "summary": summary}


# ── Dispatcher ──────────────────────────────────────────────────────────────

TOOL_MAP = {
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "lookup_appointment": lookup_appointment,
    "cancel_appointment": cancel_appointment,
    "send_confirmation": send_confirmation,
    "escalate_to_human": escalate_to_human,
    "end_call": end_call,
}


def execute_tool(tool_name: str, tool_input: dict) -> dict:
    fn = TOOL_MAP.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(**tool_input)
    except Exception as e:
        return {"error": str(e)}
