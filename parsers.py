"""
LLM-powered input extraction from free-form user text.

Uses OpenAI GPT-4o-mini to parse messy, conversational user input
into structured data. Falls back to regex when LLM is unavailable.
"""
from __future__ import annotations

import json
import os
import re
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from config import GEMINI_MODEL, GEMINI_TEMPERATURE


class ExtractedInfo(BaseModel):
    account_id: str | None = Field(default=None, description="Account ID in format ACC followed by 4 digits (e.g. ACC1001)")
    name: str | None = Field(default=None, description="Full name on account. Preserve exact casing and spelling.")
    dob: str | None = Field(default=None, description="DOB in YYYY-MM-DD format.")
    aadhaar_last4: str | None = Field(default=None, description="Last 4 digits of Aadhaar number.")
    pincode: str | None = Field(default=None, description="6-digit pincode.")
    amount: float | None = Field(default=None, description="Payment amount as a float.")
    full_amount: bool = Field(default=False, description="Whether user wants to pay full balance.")
    card_number: str | None = Field(default=None, description="Card number (digits only).")
    cvv: str | None = Field(default=None, description="Card CVV code (digits only).")
    expiry_month: int | None = Field(default=None, description="Expiry month (1-12).")
    expiry_year: int | None = Field(default=None, description="Expiry year (e.g. 2027).")
    cardholder_name: str | None = Field(default=None, description="Name on card. Preserve exact casing.")
    confirmation: bool | None = Field(default=None, description="True=yes/proceed, False=no/cancel, None=unclear.")
    cancel: bool = Field(default=False, description="True if user wants to cancel or abort.")
    intent: str | None = Field(default=None, description="Brief description of user intent.")


def _get_client() -> genai.Client | None:
    """Get Gemini client if API key is available."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


# ──────────────────────────────────────────────
# LLM Extraction (primary approach)
# ──────────────────────────────────────────────

def _llm_extract(user_input: str, current_state: str, context_summary: str) -> dict:
    """
    Use Gemini (gemini-2.5-flash) to extract structured data from free-form text.
    
    Returns a dict with any recognized fields.
    """
    client = _get_client()
    if not client:
        return _regex_extract(user_input, current_state)

    system_prompt = """You are a data extraction assistant for a payment collection agent. 
Your job is to extract structured information from the user's conversational message.

RULES:
- Extract ONLY what the user explicitly provides. Never invent or assume data.
- For names: preserve EXACT casing and spelling as the user typed it. Do not normalize or correct.
- For dates: convert to YYYY-MM-DD format. Handle natural formats like "14th May 1990", "May 14, 90", "14-05-1990".
  - "90" or "1990" → year 1990 (if context is DOB, 2-digit years in 0-99 refer to 1900s for DOB)
- For card numbers: strip ALL spaces, dashes, dots. Return digits only.
- For CVV: convert word numbers ("one two three" → "123"). Return digits only.
- For expiry: "12/27" → month=12, year=2027. "December 2027" → month=12, year=2027.
  - 2-digit years: add 2000.
- For amounts: "a thousand" → 1000.00, "five hundred" → 500.00.
  - "full amount", "clear the balance", "pay everything" → set full_amount=true.
- For Aadhaar: extract last 4 digits only.
- For pincode: extract the 6-digit number (handle spaces like "4 0 0 0 0 1" → "400001").
- For account_id: extract the ACC followed by digits. Handle "ACC 1001" → "ACC1001", case-insensitive but output uppercase.
- confirmation: true if user clearly says yes/proceed/go ahead/confirm, false if no/cancel/stop/never mind.
- cancel: true if user wants to exit, abort, or cancel the entire process."""

    user_prompt = f"""Current conversation state: {current_state}
Context: {context_summary}

User message: "{user_input}"

Extract all recognizable fields according to the schema."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=GEMINI_TEMPERATURE,
                response_mime_type="application/json",
                response_schema=ExtractedInfo,
            ),
        )
        content = response.text
        parsed = json.loads(content)
        return _normalize_extracted(parsed)
    except Exception as e:
        # Fall back to regex on any LLM failure
        print(f"[WARN] LLM extraction failed: {e}. Falling back to regex.")
        return _regex_extract(user_input, current_state)


def _normalize_extracted(data: dict) -> dict:
    """Normalize extracted data — ensure correct types and clean values."""
    result = {
        "account_id": None,
        "name": None,
        "dob": None,
        "aadhaar_last4": None,
        "pincode": None,
        "amount": None,
        "full_amount": False,
        "card_number": None,
        "cvv": None,
        "expiry_month": None,
        "expiry_year": None,
        "cardholder_name": None,
        "confirmation": None,
        "cancel": False,
        "intent": None,
    }

    # Account ID
    if data.get("account_id"):
        aid = str(data["account_id"]).upper().replace(" ", "")
        if re.match(r"^ACC\d{4}$", aid):
            result["account_id"] = aid

    # Name — preserve exact casing
    if data.get("name"):
        result["name"] = str(data["name"]).strip()

    # DOB
    if data.get("dob"):
        dob = str(data["dob"]).strip()
        # Validate it's a real date
        try:
            from datetime import datetime
            datetime.strptime(dob, "%Y-%m-%d")
            result["dob"] = dob
        except ValueError:
            pass

    # Aadhaar last 4
    if data.get("aadhaar_last4"):
        a4 = str(data["aadhaar_last4"]).strip().replace(" ", "")
        if len(a4) == 4 and a4.isdigit():
            result["aadhaar_last4"] = a4

    # Pincode
    if data.get("pincode"):
        pin = str(data["pincode"]).strip().replace(" ", "")
        if len(pin) == 6 and pin.isdigit():
            result["pincode"] = pin

    # Amount
    if data.get("amount") is not None:
        try:
            amt = float(data["amount"])
            if amt > 0:
                result["amount"] = amt
        except (ValueError, TypeError):
            pass

    # Full amount flag
    result["full_amount"] = bool(data.get("full_amount", False))

    # Card number — digits only
    if data.get("card_number"):
        cn = re.sub(r"\D", "", str(data["card_number"]))
        if 13 <= len(cn) <= 19:
            result["card_number"] = cn

    # CVV
    if data.get("cvv"):
        cvv = re.sub(r"\D", "", str(data["cvv"]))
        if 3 <= len(cvv) <= 4:
            result["cvv"] = cvv

    # Expiry
    if data.get("expiry_month") is not None:
        try:
            m = int(data["expiry_month"])
            if 1 <= m <= 12:
                result["expiry_month"] = m
        except (ValueError, TypeError):
            pass
    if data.get("expiry_year") is not None:
        try:
            y = int(data["expiry_year"])
            if 0 <= y <= 99:
                y += 2000
            result["expiry_year"] = y
        except (ValueError, TypeError):
            pass

    # Cardholder name
    if data.get("cardholder_name"):
        result["cardholder_name"] = str(data["cardholder_name"]).strip()

    # Confirmation
    result["confirmation"] = data.get("confirmation")

    # Cancel
    result["cancel"] = bool(data.get("cancel", False))

    # Intent
    if data.get("intent"):
        result["intent"] = str(data["intent"]).strip()

    return result


# ──────────────────────────────────────────────
# Regex Fallback (when LLM is unavailable)
# ──────────────────────────────────────────────

def _regex_extract(user_input: str, current_state: str) -> dict:
    """
    Basic regex-based extraction as a fallback when the LLM is unavailable.
    Less accurate with conversational input, but handles clean formats.
    """
    result = {
        "account_id": None,
        "name": None,
        "dob": None,
        "aadhaar_last4": None,
        "pincode": None,
        "amount": None,
        "full_amount": False,
        "card_number": None,
        "cvv": None,
        "expiry_month": None,
        "expiry_year": None,
        "cardholder_name": None,
        "confirmation": None,
        "cancel": False,
        "intent": None,
    }

    text = user_input.strip()

    # Account ID: ACC followed by digits (with possible space)
    acc_match = re.search(r"ACC\s*(\d{4})", text, re.IGNORECASE)
    if acc_match:
        result["account_id"] = f"ACC{acc_match.group(1)}"

    # DOB patterns
    # YYYY-MM-DD
    dob_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if dob_match:
        y, m, d = dob_match.group(1), dob_match.group(2), dob_match.group(3)
        result["dob"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    else:
        # DD-MM-YYYY or DD/MM/YYYY
        dob_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
        if dob_match:
            d, m, y = dob_match.group(1), dob_match.group(2), dob_match.group(3)
            result["dob"] = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

    # Amount
    amt_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if amt_match and current_state in ("AWAITING_PAYMENT_AMOUNT",):
        amount_str = amt_match.group(1).replace(",", "")
        try:
            result["amount"] = float(amount_str)
        except ValueError:
            pass

    # "full amount" / "clear the balance"
    if re.search(r"(full|entire|total|clear|everything|all)", text, re.IGNORECASE):
        if current_state == "AWAITING_PAYMENT_AMOUNT":
            result["full_amount"] = True

    # Card number (13-19 digits with possible spaces/dashes)
    card_match = re.search(r"(\d[\d\s\-]{12,22}\d)", text)
    if card_match:
        cn = re.sub(r"\D", "", card_match.group(1))
        if 13 <= len(cn) <= 19:
            result["card_number"] = cn

    # CVV (3-4 digits, typically after "cvv" keyword)
    cvv_match = re.search(r"(?:cvv|cvc|security)\s*(?:is|:)?\s*(\d{3,4})", text, re.IGNORECASE)
    if cvv_match:
        result["cvv"] = cvv_match.group(1)

    # Expiry: MM/YY or MM/YYYY
    exp_match = re.search(r"(\d{1,2})\s*/\s*(\d{2,4})", text)
    if exp_match:
        m, y = int(exp_match.group(1)), int(exp_match.group(2))
        if 1 <= m <= 12:
            result["expiry_month"] = m
            result["expiry_year"] = y + 2000 if y < 100 else y

    # Cardholder name (after "name" or "cardholder" keyword in card context)
    if current_state in ("AWAITING_CARD_DETAILS",):
        ch_match = re.search(
            r"(?:cardholder|holder|name)\s*(?:is|:)?\s+([A-Za-z][A-Za-z\s]+?)(?:,|$)",
            text, re.IGNORECASE,
        )
        if ch_match:
            result["cardholder_name"] = ch_match.group(1).strip()

    # Aadhaar last 4 (when in context)
    if current_state == "AWAITING_SECONDARY_FACTOR":
        a4_match = re.search(r"(\d{4})", text)
        if a4_match and not result.get("dob"):
            # Heuristic: if there's a 4-digit number and no date, it might be Aadhaar
            result["aadhaar_last4"] = a4_match.group(1)

    # Pincode (6 digits, possibly with spaces)
    pin_match = re.search(r"(?:pin\s*(?:code)?)\s*(?:is|:)?\s*(\d[\d\s]{4,10}\d)", text, re.IGNORECASE)
    if pin_match:
        pin = re.sub(r"\s", "", pin_match.group(1))
        if len(pin) == 6:
            result["pincode"] = pin

    # Confirmation
    yes_pattern = re.search(r"\b(yes|yeah|yep|yup|sure|confirm|proceed|go ahead|ok|okay|do it)\b", text, re.IGNORECASE)
    no_pattern = re.search(r"\b(no|nope|nah|cancel|stop|don't|never mind|abort)\b", text, re.IGNORECASE)
    if yes_pattern and not no_pattern:
        result["confirmation"] = True
    elif no_pattern and not yes_pattern:
        result["confirmation"] = False

    # Cancel
    cancel_pattern = re.search(r"\b(cancel|abort|quit|exit|stop|never mind)\b", text, re.IGNORECASE)
    if cancel_pattern:
        result["cancel"] = True

    # Name — for regex fallback, try extracting after "name is" or "I am" etc.
    name_match = re.search(
        r"(?:(?:my\s+)?name\s+is|i\s+am|i'm|this\s+is)\s+(.+?)(?:\.|,|$)",
        text, re.IGNORECASE,
    )
    if name_match:
        result["name"] = name_match.group(1).strip()
    elif current_state == "AWAITING_NAME" and not result.get("account_id"):
        # Context-aware fallback: if we're waiting for a name and the input
        # doesn't look like an account ID, DOB, or number, treat it as the name.
        cleaned = text.strip()
        if cleaned and not cleaned.isdigit() and not re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
            result["name"] = cleaned

    # Context-aware: in AWAITING_SECONDARY_FACTOR, if we got a DOB pattern
    # it's already captured. If not, try standalone 4-digit (aadhaar) or
    # 6-digit (pincode) numbers.
    if current_state == "AWAITING_SECONDARY_FACTOR":
        if not result.get("dob") and not result.get("aadhaar_last4") and not result.get("pincode"):
            # Try standalone 6-digit as pincode
            pin_simple = re.search(r"^(\d{6})$", text.strip())
            if pin_simple:
                result["pincode"] = pin_simple.group(1)
            else:
                # Try standalone 4-digit as aadhaar last 4
                a4_simple = re.search(r"^(\d{4})$", text.strip())
                if a4_simple:
                    result["aadhaar_last4"] = a4_simple.group(1)

    # Context-aware: in AWAITING_PAYMENT_AMOUNT, try parsing standalone numbers as amounts
    if current_state == "AWAITING_PAYMENT_AMOUNT" and not result.get("amount"):
        amt_simple = re.search(r"^[\s₹]*(\d+(?:\.\d{1,2})?)[\s]*$", text.strip())
        if amt_simple:
            try:
                result["amount"] = float(amt_simple.group(1))
            except ValueError:
                pass

    return result


# ──────────────────────────────────────────────
# Public Interface
# ──────────────────────────────────────────────

def extract(user_input: str, current_state: str, context_summary: str = "") -> dict:
    """
    Extract structured data from free-form user input.
    
    Uses LLM (GPT-4o-mini) as primary extractor, falls back to regex.
    
    Args:
        user_input: Raw text from user
        current_state: Current FSM state (helps with context-aware extraction)
        context_summary: Brief summary of conversation so far
    
    Returns:
        Dict with all recognized fields (see _llm_extract docstring)
    """
    return _llm_extract(user_input, current_state, context_summary)
