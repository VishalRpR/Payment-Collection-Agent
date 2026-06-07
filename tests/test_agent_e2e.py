"""
End-to-end conversation tests for the Payment Agent.

These tests simulate full conversations by calling agent.next() in a loop
with scripted user inputs. They verify state transitions, responses, and
that the agent follows the required flow.

NOTE: These tests use regex fallback (no LLM) for determinism.
      OPENAI_API_KEY is set to empty to force regex mode.

Run: pytest tests/test_agent_e2e.py -v
"""
import sys
import os

# Force regex mode for deterministic tests
os.environ["OPENAI_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock

from agent import Agent
from config import State


# ──────────────────────────────────────────────
# Mock API responses
# ──────────────────────────────────────────────

MOCK_ACC1001 = {
    "success": True,
    "data": {
        "account_id": "ACC1001",
        "full_name": "Nithin Jain",
        "dob": "1990-05-14",
        "aadhaar_last4": "4321",
        "pincode": "400001",
        "balance": 1250.75,
    },
}

MOCK_ACC1003_ZERO = {
    "success": True,
    "data": {
        "account_id": "ACC1003",
        "full_name": "Priya Agarwal",
        "dob": "1992-08-10",
        "aadhaar_last4": "2468",
        "pincode": "400003",
        "balance": 0.00,
    },
}

MOCK_ACC1004_LEAP = {
    "success": True,
    "data": {
        "account_id": "ACC1004",
        "full_name": "Rahul Mehta",
        "dob": "1988-02-29",
        "aadhaar_last4": "1357",
        "pincode": "400004",
        "balance": 3200.50,
    },
}

MOCK_NOT_FOUND = {
    "success": False,
    "error_code": "account_not_found",
    "message": "No account found with the provided account_id.",
}

MOCK_PAYMENT_SUCCESS = {
    "success": True,
    "transaction_id": "txn_test_12345",
}

MOCK_PAYMENT_INSUFFICIENT = {
    "success": False,
    "error_code": "insufficient_balance",
}

MOCK_PAYMENT_INVALID_CARD = {
    "success": False,
    "error_code": "invalid_card",
}


def _make_agent(mock_lookup_response):
    """Create an Agent with mocked API — injects mock AFTER construction."""
    agent = Agent()
    mock_api = MagicMock()
    mock_api.lookup_account.return_value = mock_lookup_response
    mock_api.process_payment.return_value = MOCK_PAYMENT_SUCCESS
    # Inject mock into both agent and state machine
    agent.api = mock_api
    agent.state_machine.api = mock_api
    return agent, mock_api


# ──────────────────────────────────────────────
# Test: Happy Path
# ──────────────────────────────────────────────

class TestHappyPath:
    """Full successful payment flow with ACC1001."""

    def test_full_flow(self):
        agent, mock_api = _make_agent(MOCK_ACC1001)

        # Turn 1: Greeting
        r = agent.next("Hi")
        assert "account" in r["message"].lower()

        # Turn 2: Provide account ID
        r = agent.next("My account ID is ACC1001")
        assert "name" in r["message"].lower()

        # Turn 3: Provide name (plain text, no "my name is" prefix)
        r = agent.next("Nithin Jain")
        msg = r["message"].lower()
        assert "verif" in msg or "date" in msg or "aadhaar" in msg or "pincode" in msg

        # Turn 4: Provide DOB
        r = agent.next("1990-05-14")
        msg = r["message"].lower()
        assert "verified" in msg or "balance" in msg
        assert "1,250.75" in r["message"] or "1250.75" in r["message"]

        # Turn 5: Payment amount
        r = agent.next("500")
        assert "card" in r["message"].lower()

        # Turn 6: Card details (all at once)
        r = agent.next("Card 4532015112830366, CVV 123, expiry 12/2027, name Nithin Jain")
        msg = r["message"].lower()
        assert "confirm" in msg or "card" in msg

        # Turn 7: Confirm
        r = agent.next("Yes")
        msg = r["message"].lower()
        assert "success" in msg or "transaction" in msg


# ──────────────────────────────────────────────
# Test: Verification Failure (Lockout)
# ──────────────────────────────────────────────

class TestVerificationLockout:
    """User provides wrong name 3 times → locked out."""

    def test_name_lockout(self):
        agent, _ = _make_agent(MOCK_ACC1001)

        # Greeting + account ID
        agent.next("Hi")
        agent.next("ACC1001")

        # Wrong name x3
        r1 = agent.next("Wrong Name")
        assert "doesn't match" in r1["message"].lower() or "attempt" in r1["message"].lower()

        r2 = agent.next("Another Wrong")
        assert "attempt" in r2["message"].lower() or "doesn't match" in r2["message"].lower()

        r3 = agent.next("Still Wrong")
        assert "locked" in r3["message"].lower() or "support" in r3["message"].lower()

        # Further input should be rejected
        r4 = agent.next("Nithin Jain")
        assert "locked" in r4["message"].lower()


# ──────────────────────────────────────────────
# Test: Zero Balance (ACC1003)
# ──────────────────────────────────────────────

class TestZeroBalance:
    """ACC1003 has ₹0.00 balance — should close gracefully."""

    def test_zero_balance_flow(self):
        agent, _ = _make_agent(MOCK_ACC1003_ZERO)

        agent.next("Hi")
        agent.next("ACC1003")
        agent.next("Priya Agarwal")
        r = agent.next("1992-08-10")

        assert "0.00" in r["message"] or "nothing" in r["message"].lower() or "no outstanding" in r["message"].lower()


# ──────────────────────────────────────────────
# Test: Leap Year DOB (ACC1004)
# ──────────────────────────────────────────────

class TestLeapYear:
    """ACC1004 has DOB 1988-02-29 (leap year). Verify it works."""

    def test_leap_year_dob(self):
        agent, _ = _make_agent(MOCK_ACC1004_LEAP)

        agent.next("Hi")
        agent.next("ACC1004")
        agent.next("Rahul Mehta")
        r = agent.next("1988-02-29")

        assert "verified" in r["message"].lower() or "balance" in r["message"].lower()


# ──────────────────────────────────────────────
# Test: Cancellation Mid-Flow
# ──────────────────────────────────────────────

class TestCancellation:
    """User says 'cancel' mid-flow → graceful close."""

    def test_cancel_during_verification(self):
        agent, _ = _make_agent(MOCK_ACC1001)

        agent.next("Hi")
        agent.next("ACC1001")
        r = agent.next("cancel")

        assert "cancel" in r["message"].lower() or "ended" in r["message"].lower()


# ──────────────────────────────────────────────
# Test: Account Not Found
# ──────────────────────────────────────────────

class TestAccountNotFound:
    """Invalid account ID → error message → retry."""

    def test_not_found(self):
        agent, _ = _make_agent(MOCK_NOT_FOUND)

        agent.next("Hi")
        r = agent.next("ACC9999")

        assert "couldn't find" in r["message"].lower() or "not found" in r["message"].lower()


# ──────────────────────────────────────────────
# Test: Out-of-order Input
# ──────────────────────────────────────────────

class TestOutOfOrder:
    """User provides name together with account ID."""

    def test_name_with_account_id(self):
        agent, _ = _make_agent(MOCK_ACC1001)

        agent.next("Hi")
        # User provides both account ID and name
        r = agent.next("My account is ACC1001 and my name is Nithin Jain")
        msg = r["message"].lower()
        # Should skip asking for name since it was already provided
        # Either asks for secondary factor or says name matched
        assert "name" in msg or "verif" in msg or "date" in msg or "aadhaar" in msg


# ──────────────────────────────────────────────
# Test: Aadhaar Verification
# ──────────────────────────────────────────────

class TestAadhaarVerification:
    """User verifies with Aadhaar last 4 instead of DOB."""

    def test_aadhaar_flow(self):
        agent, _ = _make_agent(MOCK_ACC1001)

        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        r = agent.next("4321")

        assert "verified" in r["message"].lower() or "balance" in r["message"].lower()
