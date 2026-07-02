from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Patient Compliance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mock patient database ──────────────────────────────────────────────────────
PATIENTS = [
    {
        "id": "P001",
        "first_name": "Maria",
        "last_name": "Gonzalez",
        "dob": "1965-03-12",
        "phone": "5551234567",
        "compliance_status": "Compliant",
        "days_left_for_compliance": 90,
        "days_needed_for_compliance": 0,
    },
    {
        "id": "P002",
        "first_name": "James",
        "last_name": "Thompson",
        "dob": "1978-07-22",
        "phone": "5559876543",
        "compliance_status": "Non-Compliant",
        "days_left_for_compliance": 14,
        "days_needed_for_compliance": 30,
    },
    {
        "id": "P003",
        "first_name": "Linda",
        "last_name": "Patel",
        "dob": "1990-11-05",
        "phone": "5554445678",
        "compliance_status": "In Progress",
        "days_left_for_compliance": 45,
        "days_needed_for_compliance": 15,
    },
    {
        "id": "P004",
        "first_name": "Robert",
        "last_name": "Kim",
        "dob": "1955-01-30",
        "phone": "5552223333",
        "compliance_status": "Non-Compliant",
        "days_left_for_compliance": 5,
        "days_needed_for_compliance": 60,
    },
    {
        "id": "P005",
        "first_name": "Susan",
        "last_name": "Carter",
        "dob": "1982-09-18",
        "phone": "5556667777",
        "compliance_status": "In Progress",
        "days_left_for_compliance": 30,
        "days_needed_for_compliance": 10,
    },
    {
        "id": "P006",
        "first_name": "Cyrus",
        "last_name": "Mirzaie",
        "dob": "2004-03-15",
        "phone": "6157526249",
        "compliance_status": "In Progress",
        "days_left_for_compliance": 12,
        "days_needed_for_compliance": 8,
    },
]


# ── Agent availability config ───────────────────────────────────────────────────
BUSINESS_TIMEZONE = "America/Chicago"  # Central Time (handles CST/CDT automatically)
BUSINESS_DAYS = range(0, 5)            # Monday(0) - Friday(4)
BUSINESS_START_HOUR = 9                # 9:00 AM
BUSINESS_END_HOUR = 17                 # 5:00 PM


def is_within_business_hours(now: datetime) -> bool:
    return now.weekday() in BUSINESS_DAYS and BUSINESS_START_HOUR <= now.hour < BUSINESS_END_HOUR


def check_sanusom_agent_availability() -> Optional[bool]:
    """
    Placeholder for a future integration that asks Sanusom staff directly
    (e.g. an on-call/staffing system) whether a live agent is available.

    Returns None until that integration exists, meaning "no signal" —
    the business-hours check below is used as the sole source of truth
    for now. Once implemented, this should return True/False and be
    combined with the business-hours check in agent_availability().
    """
    return None


def build_response(patient: dict) -> dict:
    return {
        "found": True,
        "patient_id": patient["id"],
        "patient_name": f"{patient['first_name']} {patient['last_name']}",
        "compliance_status": patient["compliance_status"],
        "days_left": patient["days_left_for_compliance"],
        "days_needed": patient["days_needed_for_compliance"],
    }


# ── Request models ─────────────────────────────────────────────────────────────
class PhoneLookupRequest(BaseModel):
    phone: str  # digits only or formatted, e.g. "5551234567" or "555-123-4567"

class NameDobLookupRequest(BaseModel):
    first_name: str
    last_name: str
    dob: str  # YYYY-MM-DD


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Patient Compliance API is running"}


@app.post("/lookup/phone")
def lookup_by_phone(req: PhoneLookupRequest):
    """
    Look up a patient by phone number.
    Strips all non-digit characters before matching.
    """
    digits = "".join(filter(str.isdigit, req.phone))
    for p in PATIENTS:
        if p["phone"] == digits:
            return build_response(p)
    return {"found": False, "message": "No patient found with that phone number."}


@app.post("/lookup/name-dob")
def lookup_by_name_dob(req: NameDobLookupRequest):
    """
    Look up a patient by first name, last name, and date of birth.
    Case-insensitive name matching.
    """
    for p in PATIENTS:
        if (
            p["first_name"].lower() == req.first_name.strip().lower()
            and p["last_name"].lower() == req.last_name.strip().lower()
            and p["dob"] == req.dob
        ):
            return build_response(p)
    return {"found": False, "message": "No patient found with that name and date of birth."}


@app.get("/availability/agent")
def agent_availability():
    """
    Lets AurionX check whether an agent is available before/during a call flow.

    Currently checks business hours only (Mon-Fri, 9:00 AM-5:00 PM Central).
    Future: will also check live Sanusom staff availability and combine
    that signal with the business-hours check below.
    """
    now = datetime.now(ZoneInfo(BUSINESS_TIMEZONE))
    within_hours = is_within_business_hours(now)

    # Not yet wired up — see check_sanusom_agent_availability() docstring.
    _sanusom_available = check_sanusom_agent_availability()  # noqa: F841 (reserved for future use)

    available = within_hours

    return {
        "available": available,
        "reason": "Within business hours" if within_hours else "Outside business hours",
        "checked_at": now.isoformat(),
        "timezone": BUSINESS_TIMEZONE,
        "business_hours": "Mon-Fri, 9:00 AM-5:00 PM CT",
    }
