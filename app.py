from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
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
    {
        "id": "P007",
        "first_name": "Lynda",
        "last_name": "Bolan",
        "dob": "2000-01-01",
        "phone": "6154787186",
        "compliance_status": "In Progress",
        "days_left_for_compliance": 20,
        "days_needed_for_compliance": 10,
    }
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


# ── Request parsing ────────────────────────────────────────────────────────────
async def read_call_args(request: Request) -> dict:
    """
    Reads the JSON body and returns just the actual parameters, regardless
    of whether the caller posts them flat (e.g. {"phone": "..."}) or
    wrapped in Retell's Custom Function envelope
    (e.g. {"call": {...}, "name": "...", "args": {"phone": "..."}}).

    Retell's Custom Function tool wraps parameters under "args" by
    default (per docs.retellai.com/build/custom-function); this lets one
    endpoint handle both that format and a plain flat body (e.g. from
    Postman or another integration) without needing every caller to
    match the same shape.
    """
    try:
        payload = await request.json()
    except Exception:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("args"), dict):
        return payload["args"]
    return payload if isinstance(payload, dict) else {}


# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Patient Compliance API is running"}


def normalize_phone(phone: str) -> str:
    """
    Normalize a phone number to its last 10 digits.
    Strips non-digit characters (spaces, dashes, parens, '+') and drops a
    leading '1' US country code (e.g. "+16157526249" -> "6157526249"),
    so incoming and stored numbers match regardless of whether either
    side includes a country code.
    """
    digits = "".join(filter(str.isdigit, phone))
    return digits[-10:] if len(digits) >= 10 else digits


@app.post("/lookup/phone")
async def lookup_by_phone(request: Request):
    """
    Look up a patient by phone number.
    Matches on the last 10 digits, so a leading country code
    (e.g. "+1") on either side doesn't break the lookup.
    Accepts either a flat body ({"phone": "..."}) or Retell's
    Custom Function envelope ({"args": {"phone": "..."}, ...}).
    """
    args = await read_call_args(request)
    phone = str(args.get("phone", "")).strip()
    if not phone or phone == "{{user_number}}":
        return {"found": False, "message": "No phone number provided."}
    digits = normalize_phone(phone)
    for p in PATIENTS:
        if normalize_phone(p["phone"]) == digits:
            return build_response(p)
    return {"found": False, "message": "No patient found with that phone number."}


@app.post("/lookup/name-dob")
async def lookup_by_name_dob(request: Request):
    """
    Look up a patient by first name, last name, and date of birth.
    Case-insensitive name matching.
    Accepts either a flat body or Retell's Custom Function envelope.
    """
    args = await read_call_args(request)
    first_name = str(args.get("first_name", "")).strip()
    last_name = str(args.get("last_name", "")).strip()
    dob = str(args.get("dob", "")).strip()
    if not (first_name and last_name and dob):
        return {"found": False, "message": "Missing first_name, last_name, or dob."}
    for p in PATIENTS:
        if (
            p["first_name"].lower() == first_name.lower()
            and p["last_name"].lower() == last_name.lower()
            and p["dob"] == dob
        ):
            return build_response(p)
    return {"found": False, "message": "No patient found with that name and date of birth."}


@app.get("/agent")
def agent_availability(response: Response):
    """
    Lets AurionX check whether an agent is available before/during a call flow.

    Currently checks business hours only (Mon-Fri, 9:00 AM-5:00 PM Central).
    Future: will also check live Sanusom staff availability and combine
    that signal with the business-hours check below.

    Returns HTTP 200 when available and HTTP 404 when not, in addition to
    the JSON body, so this works with AurionX's "Check (HTTP Status Code)"
    connection mode out of the box (200 -> true, 404 -> false).
    """
    now = datetime.now(ZoneInfo(BUSINESS_TIMEZONE))
    within_hours = is_within_business_hours(now)

    # Not yet wired up — see check_sanusom_agent_availability() docstring.
    _sanusom_available = check_sanusom_agent_availability()  # noqa: F841 (reserved for future use)

    available = within_hours
    if not available:
        response.status_code = status.HTTP_404_NOT_FOUND

    return {
        "available": available,
        "reason": "Within business hours" if within_hours else "Outside business hours",
        "checked_at": now.isoformat(),
        "timezone": BUSINESS_TIMEZONE,
        "business_hours": "Mon-Fri, 9:00 AM-5:00 PM CT",
    }
