"""
Conversation context management.

Maintains all state across turns — account data, collected user inputs,
verification progress, payment progress, and conversation history.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import State


@dataclass
class CardDetails:
    """Collected card payment details."""
    cardholder_name: str | None = None
    card_number: str | None = None       # digits only, no spaces
    cvv: str | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None

    def is_complete(self) -> bool:
        return all([
            self.cardholder_name,
            self.card_number,
            self.cvv,
            self.expiry_month is not None,
            self.expiry_year is not None,
        ])

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.cardholder_name:
            missing.append("cardholder name")
        if not self.card_number:
            missing.append("card number")
        if not self.cvv:
            missing.append("CVV")
        if self.expiry_month is None or self.expiry_year is None:
            missing.append("expiry date (month and year)")
        return missing

    def to_api_payload(self) -> dict:
        return {
            "cardholder_name": self.cardholder_name,
            "card_number": self.card_number,
            "cvv": self.cvv,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
        }

    def masked_number(self) -> str:
        if self.card_number and len(self.card_number) >= 4:
            return f"****{self.card_number[-4:]}"
        return "****"

    def clear(self):
        """Wipe card data after payment attempt for security."""
        self.cardholder_name = None
        self.card_number = None
        self.cvv = None
        self.expiry_month = None
        self.expiry_year = None


@dataclass
class ConversationContext:
    """
    Holds all conversational state between turns.
    
    Security: account_data contains PII from the API and must NEVER
    be exposed in agent responses.
    """

    # --- Flow state ---
    current_state: str = State.GREETING

    # --- Account data (from API — NEVER expose to user) ---
    account_data: dict[str, Any] | None = None

    # --- Collected user data ---
    provided_account_id: str | None = None
    provided_name: str | None = None
    provided_dob: str | None = None
    provided_aadhaar_last4: str | None = None
    provided_pincode: str | None = None
    provided_amount: float | None = None
    provided_card: CardDetails = field(default_factory=CardDetails)

    # --- Verification tracking ---
    name_verified: bool = False
    secondary_verified: bool = False
    verification_attempts: int = 0

    # --- Payment tracking ---
    payment_attempts: int = 0
    transaction_id: str | None = None

    # --- Account lookup tracking ---
    account_lookup_attempts: int = 0

    # --- Conversation history (for LLM context) ---
    messages: list[dict[str, str]] = field(default_factory=list)

    def add_user_message(self, text: str):
        self.messages.append({"role": "user", "content": text})

    def add_agent_message(self, text: str):
        self.messages.append({"role": "assistant", "content": text})

    @property
    def balance(self) -> float | None:
        if self.account_data:
            return self.account_data.get("balance")
        return None

    @property
    def account_name(self) -> str | None:
        if self.account_data:
            return self.account_data.get("full_name")
        return None

    def clear_card_data(self):
        """Security: wipe card data after use."""
        self.provided_card.clear()
