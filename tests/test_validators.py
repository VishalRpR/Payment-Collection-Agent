"""
Unit tests for validators.py

Run: pytest tests/test_validators.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from validators import (
    validate_account_id,
    validate_name,
    validate_dob,
    validate_aadhaar_last4,
    validate_pincode,
    validate_amount,
    luhn_check,
    validate_card_number,
    validate_cvv,
    validate_expiry,
    validate_card_details,
    is_amex,
)


# ──────────────────────────────────────────────
# Account ID
# ──────────────────────────────────────────────

class TestAccountId:
    def test_valid(self):
        assert validate_account_id("ACC1001") is True
        assert validate_account_id("ACC0000") is True
        assert validate_account_id("ACC9999") is True

    def test_invalid_format(self):
        assert validate_account_id("acc1001") is False   # lowercase
        assert validate_account_id("AC1001") is False    # missing C
        assert validate_account_id("ACC10011") is False  # too many digits
        assert validate_account_id("ACC100") is False    # too few digits
        assert validate_account_id("1001") is False      # no prefix
        assert validate_account_id("") is False


# ──────────────────────────────────────────────
# Name Verification
# ──────────────────────────────────────────────

class TestNameValidation:
    def test_exact_match(self):
        assert validate_name("Nithin Jain", "Nithin Jain") is True

    def test_case_sensitive(self):
        # Strict: no case-insensitive workarounds
        assert validate_name("nithin jain", "Nithin Jain") is False
        assert validate_name("NITHIN JAIN", "Nithin Jain") is False

    def test_whitespace_trimming(self):
        assert validate_name("  Nithin Jain  ", "Nithin Jain") is True

    def test_long_name(self):
        assert validate_name("Rajarajeswari Balasubramaniam", "Rajarajeswari Balasubramaniam") is True

    def test_wrong_name(self):
        assert validate_name("Nithin Kumar", "Nithin Jain") is False

    def test_partial_name(self):
        assert validate_name("Nithin", "Nithin Jain") is False


# ──────────────────────────────────────────────
# Date of Birth
# ──────────────────────────────────────────────

class TestDobValidation:
    def test_exact_match(self):
        assert validate_dob("1990-05-14", "1990-05-14") is True

    def test_mismatch(self):
        assert validate_dob("1990-05-15", "1990-05-14") is False

    def test_leap_year_valid(self):
        # 1988 is a leap year, Feb 29 is valid
        assert validate_dob("1988-02-29", "1988-02-29") is True

    def test_leap_year_invalid(self):
        # 1989 is NOT a leap year, Feb 29 is invalid
        assert validate_dob("1989-02-29", "1988-02-29") is False

    def test_invalid_date(self):
        assert validate_dob("not-a-date", "1990-05-14") is False
        assert validate_dob("1990-13-14", "1990-05-14") is False

    def test_wrong_month(self):
        assert validate_dob("1988-02-28", "1988-02-29") is False


# ──────────────────────────────────────────────
# Aadhaar Last 4
# ──────────────────────────────────────────────

class TestAadhaarValidation:
    def test_match(self):
        assert validate_aadhaar_last4("4321", "4321") is True

    def test_mismatch(self):
        assert validate_aadhaar_last4("4322", "4321") is False

    def test_non_digits(self):
        assert validate_aadhaar_last4("abcd", "4321") is False

    def test_wrong_length(self):
        assert validate_aadhaar_last4("432", "4321") is False
        assert validate_aadhaar_last4("43210", "4321") is False


# ──────────────────────────────────────────────
# Pincode
# ──────────────────────────────────────────────

class TestPincodeValidation:
    def test_match(self):
        assert validate_pincode("400001", "400001") is True

    def test_mismatch(self):
        assert validate_pincode("400002", "400001") is False

    def test_wrong_length(self):
        assert validate_pincode("40000", "400001") is False
        assert validate_pincode("4000011", "400001") is False


# ──────────────────────────────────────────────
# Payment Amount
# ──────────────────────────────────────────────

class TestAmountValidation:
    def test_valid_partial(self):
        valid, err = validate_amount(500.00, 1250.75)
        assert valid is True
        assert err is None

    def test_valid_full(self):
        valid, err = validate_amount(1250.75, 1250.75)
        assert valid is True

    def test_exceeds_balance(self):
        valid, err = validate_amount(2000.00, 1250.75)
        assert valid is False
        assert "exceeds" in err.lower()

    def test_zero(self):
        valid, err = validate_amount(0, 1250.75)
        assert valid is False

    def test_negative(self):
        valid, err = validate_amount(-100, 1250.75)
        assert valid is False

    def test_too_many_decimals(self):
        valid, err = validate_amount(100.123, 1250.75)
        assert valid is False
        assert "decimal" in err.lower()


# ──────────────────────────────────────────────
# Luhn Check
# ──────────────────────────────────────────────

class TestLuhnCheck:
    def test_valid_visa(self):
        assert luhn_check("4532015112830366") is True

    def test_valid_mastercard(self):
        assert luhn_check("5425233430109903") is True

    def test_invalid(self):
        assert luhn_check("4532015112830367") is False

    def test_non_digits(self):
        assert luhn_check("abcdefgh") is False

    def test_empty(self):
        assert luhn_check("") is False


# ──────────────────────────────────────────────
# Card Number
# ──────────────────────────────────────────────

class TestCardNumber:
    def test_valid(self):
        valid, err = validate_card_number("4532015112830366")
        assert valid is True

    def test_too_short(self):
        valid, err = validate_card_number("453201")
        assert valid is False

    def test_luhn_fail(self):
        valid, err = validate_card_number("4532015112830367")
        assert valid is False


# ──────────────────────────────────────────────
# CVV
# ──────────────────────────────────────────────

class TestCvv:
    def test_valid_3_digit(self):
        valid, err = validate_cvv("123", "4532015112830366")
        assert valid is True

    def test_invalid_2_digit(self):
        valid, err = validate_cvv("12", "4532015112830366")
        assert valid is False

    def test_amex_4_digit(self):
        # Amex starts with 34 or 37
        valid, err = validate_cvv("1234", "340000000000009")
        assert valid is True

    def test_amex_3_digit_fails(self):
        valid, err = validate_cvv("123", "340000000000009")
        assert valid is False


# ──────────────────────────────────────────────
# Expiry
# ──────────────────────────────────────────────

class TestExpiry:
    def test_future_date(self):
        valid, err = validate_expiry(12, 2027)
        assert valid is True

    def test_expired(self):
        valid, err = validate_expiry(1, 2020)
        assert valid is False
        assert "expired" in err.lower()

    def test_invalid_month(self):
        valid, err = validate_expiry(13, 2027)
        assert valid is False

    def test_zero_month(self):
        valid, err = validate_expiry(0, 2027)
        assert valid is False

    def test_2_digit_year(self):
        valid, err = validate_expiry(12, 27)
        assert valid is True  # Normalizes to 2027


# ──────────────────────────────────────────────
# Full Card Validation
# ──────────────────────────────────────────────

class TestFullCardValidation:
    def test_all_valid(self):
        valid, errors = validate_card_details("4532015112830366", "123", 12, 2027)
        assert valid is True
        assert errors == []

    def test_multiple_errors(self):
        valid, errors = validate_card_details("0000000000000000", "12", 13, 2020)
        assert valid is False
        assert len(errors) >= 2  # At least card + cvv + expiry errors
