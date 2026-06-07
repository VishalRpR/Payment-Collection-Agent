"""
Deterministic validators for the Payment Collection Agent.

All validation here is pure Python — no LLM involvement.
These functions validate structured/parsed data, NOT raw user input.
"""
from __future__ import annotations

import re
from datetime import date, datetime


# ──────────────────────────────────────────────
# Account ID
# ──────────────────────────────────────────────

def validate_account_id(account_id: str) -> bool:
    """Check if the account ID matches the expected format: ACC followed by 4 digits."""
    return bool(re.match(r"^ACC\d{4}$", account_id))


# ──────────────────────────────────────────────
# Name Verification (STRICT)
# ──────────────────────────────────────────────

def validate_name(provided: str, expected: str) -> bool:
    """
    Exact string match — case-sensitive, whitespace-trimmed.
    
    Per the assignment: "Matching is strict — no fuzzy matching,
    no case-insensitive workarounds for names."
    
    We strip leading/trailing whitespace but preserve internal spacing and case.
    """
    return provided.strip() == expected.strip()


# ──────────────────────────────────────────────
# Date of Birth
# ──────────────────────────────────────────────

def validate_dob(provided: str, expected: str) -> bool:
    """
    Compare DOB strings in YYYY-MM-DD format.
    Both must be valid dates (handles leap years automatically).
    """
    try:
        provided_date = datetime.strptime(provided.strip(), "%Y-%m-%d").date()
        expected_date = datetime.strptime(expected.strip(), "%Y-%m-%d").date()
        return provided_date == expected_date
    except ValueError:
        return False


def is_valid_date_string(date_str: str) -> bool:
    """Check if a string is a valid YYYY-MM-DD date."""
    try:
        datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


# ──────────────────────────────────────────────
# Aadhaar Last 4
# ──────────────────────────────────────────────

def validate_aadhaar_last4(provided: str, expected: str) -> bool:
    """Exact 4-digit string match."""
    return (
        provided.strip() == expected.strip()
        and len(provided.strip()) == 4
        and provided.strip().isdigit()
    )


# ──────────────────────────────────────────────
# Pincode
# ──────────────────────────────────────────────

def validate_pincode(provided: str, expected: str) -> bool:
    """Exact 6-digit string match."""
    return (
        provided.strip() == expected.strip()
        and len(provided.strip()) == 6
        and provided.strip().isdigit()
    )


# ──────────────────────────────────────────────
# Payment Amount
# ──────────────────────────────────────────────

def validate_amount(amount: float, balance: float) -> tuple[bool, str | None]:
    """
    Validate payment amount against the account balance.
    
    Returns:
        (is_valid, error_reason) — error_reason is None if valid.
    """
    if amount <= 0:
        return False, "Amount must be greater than zero."
    if amount > balance:
        return False, f"Amount (₹{amount:.2f}) exceeds your outstanding balance of ₹{balance:.2f}."

    # Check max 2 decimal places
    amount_str = f"{amount:.10f}"
    decimal_part = amount_str.split(".")[1]
    if decimal_part.rstrip("0") and len(decimal_part.rstrip("0")) > 2:
        return False, "Amount can have at most 2 decimal places."

    return True, None


# ──────────────────────────────────────────────
# Card Number — Luhn Check
# ──────────────────────────────────────────────

def luhn_check(card_number: str) -> bool:
    """
    Standard Luhn algorithm to validate a credit card number.
    Input should be digits only (no spaces or dashes).
    """
    digits = card_number.strip()
    if not digits.isdigit():
        return False

    total = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_card_number(card_number: str) -> tuple[bool, str | None]:
    """
    Validate card number: length (13-19 digits) and Luhn check.
    
    Returns:
        (is_valid, error_reason)
    """
    digits = re.sub(r"\s+", "", card_number.strip())
    if not digits.isdigit():
        return False, "Card number should contain only digits."
    if len(digits) < 13 or len(digits) > 19:
        return False, f"Card number should be 13-19 digits (got {len(digits)})."
    if not luhn_check(digits):
        return False, "Card number is not valid (failed checksum)."
    return True, None


# ──────────────────────────────────────────────
# CVV
# ──────────────────────────────────────────────

def is_amex(card_number: str) -> bool:
    """Check if a card number is American Express (starts with 34 or 37)."""
    digits = re.sub(r"\s+", "", card_number.strip())
    return digits.startswith("34") or digits.startswith("37")


def validate_cvv(cvv: str, card_number: str | None = None) -> tuple[bool, str | None]:
    """
    Validate CVV: 3 digits for standard cards, 4 digits for Amex.
    
    Returns:
        (is_valid, error_reason)
    """
    cvv = cvv.strip()
    if not cvv.isdigit():
        return False, "CVV should contain only digits."

    expected_len = 4 if (card_number and is_amex(card_number)) else 3
    if len(cvv) != expected_len:
        if expected_len == 4:
            return False, "For American Express cards, CVV should be 4 digits."
        else:
            return False, "CVV should be 3 digits."
    return True, None


# ──────────────────────────────────────────────
# Expiry Date
# ──────────────────────────────────────────────

def validate_expiry(month: int, year: int) -> tuple[bool, str | None]:
    """
    Validate card expiry: month 1-12, not expired.
    Year can be 2-digit or 4-digit.
    
    Returns:
        (is_valid, error_reason)
    """
    # Normalize 2-digit year
    if 0 <= year <= 99:
        year += 2000

    if month < 1 or month > 12:
        return False, "Expiry month must be between 1 and 12."

    today = date.today()
    # Card expires at the end of the expiry month
    try:
        if year < today.year or (year == today.year and month < today.month):
            return False, "This card has expired."
    except Exception:
        return False, "Invalid expiry date."

    return True, None


# ──────────────────────────────────────────────
# Full Card Validation (client-side pre-check)
# ──────────────────────────────────────────────

def validate_card_details(card_number: str, cvv: str, expiry_month: int, expiry_year: int) -> tuple[bool, list[str]]:
    """
    Validate all card fields client-side before calling the API.
    
    Returns:
        (all_valid, list_of_error_messages)
    """
    errors = []

    valid, err = validate_card_number(card_number)
    if not valid:
        errors.append(err)

    valid, err = validate_cvv(cvv, card_number)
    if not valid:
        errors.append(err)

    valid, err = validate_expiry(expiry_month, expiry_year)
    if not valid:
        errors.append(err)

    return len(errors) == 0, errors
