"""
Simulated calendar for Berkeley Optometry Clinic.

Realistic time logic: 30-min slots, clinic hours, lunch block,
duration-aware booking, conflict detection, and rescheduling.
"""

import json
import os
from datetime import datetime, timedelta, time

# ── Clinic Configuration ────────────────────────────────────────────────────

CLINIC_OPEN = time(9, 0)       # 9:00 AM
CLINIC_CLOSE = time(17, 0)     # 5:00 PM
LUNCH_START = time(12, 0)      # 12:00 PM
LUNCH_END = time(13, 0)        # 1:00 PM
SLOT_MINUTES = 30
BOOKING_WINDOW_DAYS = 30
HOLIDAYS = []  # Add date strings like "2026-04-10" as needed

APPOINTMENT_DURATIONS = {
    "new_patient": {"slots": 2, "buffer_slots": 1},   # 60 min + 15 min buffer (rounds to 1 slot)
    "follow_up":   {"slots": 1, "buffer_slots": 0},   # 30 min, no buffer
}

DATA_FILE = os.path.join(os.path.dirname(__file__), "calendar_data.json")


# ── Data Persistence ────────────────────────────────────────────────────────

def _load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"appointments": [], "next_id": 10001}


def _save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Slot Generation ─────────────────────────────────────────────────────────

def _generate_day_slots(date: datetime) -> list[datetime]:
    """Generate all 30-min slots for a given workday, excluding lunch."""
    slots = []
    current = datetime.combine(date.date(), CLINIC_OPEN)
    end = datetime.combine(date.date(), CLINIC_CLOSE)
    lunch_s = datetime.combine(date.date(), LUNCH_START)
    lunch_e = datetime.combine(date.date(), LUNCH_END)

    while current < end:
        if current < lunch_s or current >= lunch_e:
            slots.append(current)
        current += timedelta(minutes=SLOT_MINUTES)

    return slots


def _is_workday(date: datetime) -> bool:
    """Monday-Friday, not a holiday."""
    if date.weekday() >= 5:
        return False
    if date.strftime("%Y-%m-%d") in HOLIDAYS:
        return False
    return True


def _get_booked_ranges(data: dict) -> list[tuple[datetime, datetime]]:
    """Return list of (start, end) for all active appointments."""
    ranges = []
    for appt in data["appointments"]:
        if appt.get("cancelled"):
            continue
        start = datetime.fromisoformat(appt["start"])
        end = datetime.fromisoformat(appt["end"])
        ranges.append((start, end))
    return ranges


def _slot_available(slot: datetime, needed_slots: int, booked_ranges: list) -> bool:
    """Check if consecutive slots starting at `slot` are free."""
    appt_end = slot + timedelta(minutes=SLOT_MINUTES * needed_slots)

    # Can't exceed clinic close
    close = datetime.combine(slot.date(), CLINIC_CLOSE)
    if appt_end > close:
        return False

    # Can't overlap lunch
    lunch_s = datetime.combine(slot.date(), LUNCH_START)
    lunch_e = datetime.combine(slot.date(), LUNCH_END)
    if slot < lunch_e and appt_end > lunch_s:
        # Check if the appointment spans into or across lunch
        if not (appt_end <= lunch_s or slot >= lunch_e):
            return False

    # Can't overlap existing appointments
    for booked_start, booked_end in booked_ranges:
        if slot < booked_end and appt_end > booked_start:
            return False

    return True


# ── Public API (called by tools.py) ─────────────────────────────────────────

def check_availability(preferred_date: str, appointment_type: str,
                       preferred_time: str = "") -> dict:
    """
    Find available slots near the preferred date/time.
    Returns up to 4 options.
    """
    data = _load_data()
    booked = _get_booked_ranges(data)
    duration = APPOINTMENT_DURATIONS.get(appointment_type, APPOINTMENT_DURATIONS["follow_up"])
    needed = duration["slots"] + duration["buffer_slots"]

    # Parse preferred date — try common formats
    target_date = _parse_date(preferred_date)
    if not target_date:
        return {"error": "Could not understand the date. Please try again with a specific date."}

    # Check booking window
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    min_date = today + timedelta(days=1)
    max_date = today + timedelta(days=BOOKING_WINDOW_DAYS)

    if target_date < min_date:
        return {
            "available_slots": [],
            "message": "That date is too soon. The earliest I can book is tomorrow.",
        }
    if target_date > max_date:
        return {
            "available_slots": [],
            "message": f"I can only book up to {BOOKING_WINDOW_DAYS} days out. "
                       f"The latest available date is {max_date.strftime('%A %B %d')}.",
        }

    # Parse time preference
    morning = afternoon = False
    if preferred_time:
        pt = preferred_time.lower()
        if "morning" in pt or "am" in pt:
            morning = True
        elif "afternoon" in pt or "pm" in pt:
            afternoon = True

    # Search target date and nearby dates
    available = []
    for offset in range(0, 8):  # Check up to 8 days out from preference
        check_date = target_date + timedelta(days=offset)
        if check_date > max_date:
            break
        if not _is_workday(check_date):
            continue

        day_slots = _generate_day_slots(check_date)
        for slot in day_slots:
            if not _slot_available(slot, needed, booked):
                continue

            # Apply time preference filter for the target date
            if offset == 0:
                if morning and slot.hour >= 12:
                    continue
                if afternoon and slot.hour < 12:
                    continue

            available.append({
                "date": slot.strftime("%A %B %d"),
                "time": slot.strftime("%I:%M %p").lstrip("0"),
                "datetime_iso": slot.isoformat(),
            })

            if len(available) >= 4:
                break
        if len(available) >= 4:
            break

    return {
        "available_slots": available,
        "appointment_type": appointment_type,
        "duration_minutes": duration["slots"] * SLOT_MINUTES,
        "clinic_hours": "Monday through Friday, 9 AM to 5 PM, closed 12 to 1 for lunch",
    }


def book_appointment(patient_name: str, phone_number: str,
                     appointment_type: str, date: str, time_str: str) -> dict:
    """Book an appointment. Returns confirmation details."""
    data = _load_data()
    booked = _get_booked_ranges(data)
    duration = APPOINTMENT_DURATIONS.get(appointment_type, APPOINTMENT_DURATIONS["follow_up"])
    needed = duration["slots"] + duration["buffer_slots"]

    # Parse the date and time
    start = _parse_datetime(date, time_str)
    if not start:
        return {"success": False, "error": "Could not parse the date and time. Please try again."}

    # Verify slot is still available
    if not _slot_available(start, needed, booked):
        return {
            "success": False,
            "error": "That slot is no longer available. Please check availability again.",
        }

    # Check for returning patient
    existing = [a for a in data["appointments"]
                if not a.get("cancelled")
                and a["patient_name"].lower() == patient_name.lower()
                and a["phone_number"] == phone_number]

    end = start + timedelta(minutes=duration["slots"] * SLOT_MINUTES)
    conf_id = f"BOC{data['next_id']}"
    data["next_id"] += 1

    appointment = {
        "confirmation_id": conf_id,
        "patient_name": patient_name,
        "phone_number": phone_number,
        "appointment_type": appointment_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "cancelled": False,
        "booked_at": datetime.now().isoformat(),
    }
    data["appointments"].append(appointment)
    _save_data(data)

    result = {
        "success": True,
        "confirmation_id": conf_id,
        "patient_name": patient_name,
        "appointment_type": appointment_type,
        "date": start.strftime("%A %B %d"),
        "time": start.strftime("%I:%M %p").lstrip("0"),
        "duration_minutes": duration["slots"] * SLOT_MINUTES,
    }

    if existing:
        upcoming = [a for a in existing if datetime.fromisoformat(a["start"]) > datetime.now()]
        if upcoming:
            result["note"] = (
                f"This patient already has an upcoming appointment on "
                f"{datetime.fromisoformat(upcoming[0]['start']).strftime('%B %d at %I:%M %p')}."
            )

    return result


def lookup_appointment(patient_name: str = "", phone_number: str = "",
                       confirmation_id: str = "") -> dict:
    """Look up an existing appointment by name+phone or confirmation ID."""
    data = _load_data()
    matches = []

    for appt in data["appointments"]:
        if appt.get("cancelled"):
            continue
        # Only look at future appointments
        if datetime.fromisoformat(appt["start"]) < datetime.now():
            continue

        if confirmation_id and appt["confirmation_id"] == confirmation_id:
            matches.append(appt)
        elif (patient_name and phone_number
              and appt["patient_name"].lower() == patient_name.lower()
              and appt["phone_number"] == phone_number):
            matches.append(appt)

    if not matches:
        return {"found": False, "message": "No upcoming appointment found with that information."}

    return {
        "found": True,
        "appointments": [{
            "confirmation_id": a["confirmation_id"],
            "date": datetime.fromisoformat(a["start"]).strftime("%A %B %d"),
            "time": datetime.fromisoformat(a["start"]).strftime("%I:%M %p").lstrip("0"),
            "appointment_type": a["appointment_type"],
            "patient_name": a["patient_name"],
        } for a in matches],
    }


def cancel_appointment(confirmation_id: str) -> dict:
    """Cancel an appointment by confirmation ID."""
    data = _load_data()

    for appt in data["appointments"]:
        if appt["confirmation_id"] == confirmation_id and not appt.get("cancelled"):
            appt["cancelled"] = True
            _save_data(data)
            return {
                "success": True,
                "cancelled_id": confirmation_id,
                "message": f"Appointment {confirmation_id} has been cancelled.",
            }

    return {"success": False, "error": "Appointment not found or already cancelled."}


# ── Date Parsing Helpers ────────────────────────────────────────────────────

def _parse_date(text: str) -> datetime | None:
    """Parse natural-language-ish date strings into a datetime (date only)."""
    text = text.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Relative dates
    if text in ("tomorrow",):
        return today + timedelta(days=1)
    if text in ("today",):
        return today

    # "next monday", "next tuesday", etc.
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, name in enumerate(day_names):
        if name in text:
            days_ahead = (i - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7 if "next" in text else 0
            if "next" in text and days_ahead <= 7:
                days_ahead += 7 if days_ahead == 0 else 0
            return today + timedelta(days=max(days_ahead, 1))

    # Try standard formats
    for fmt in ("%B %d", "%B %d %Y", "%m/%d/%Y", "%m/%d", "%Y-%m-%d",
                "%b %d", "%b %d %Y", "%A %B %d", "%A %b %d"):
        try:
            parsed = datetime.strptime(text, fmt)
            # If no year in format, assume current or next year
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
                if parsed < today:
                    parsed = parsed.replace(year=today.year + 1)
            return parsed
        except ValueError:
            continue

    return None


def _parse_datetime(date_str: str, time_str: str) -> datetime | None:
    """Parse date + time strings into a datetime."""
    date = _parse_date(date_str)
    if not date:
        return None

    time_str = time_str.strip().upper()
    for fmt in ("%I:%M %p", "%I %p", "%I:%M%p", "%I%p", "%H:%M"):
        try:
            t = datetime.strptime(time_str, fmt)
            return date.replace(hour=t.hour, minute=t.minute)
        except ValueError:
            continue

    return None
