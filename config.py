"""
Configuration constants for the Payment Collection Agent.
"""

# --- API ---
API_BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com"
LOOKUP_ENDPOINT = "/api/lookup-account"
PAYMENT_ENDPOINT = "/api/process-payment"
API_TIMEOUT_SECONDS = 15

# --- Retry Limits ---
MAX_VERIFICATION_ATTEMPTS = 3   # Total attempts across name + secondary factor
MAX_PAYMENT_ATTEMPTS = 3        # Max times user can retry payment
MAX_ACCOUNT_LOOKUP_ATTEMPTS = 3 # Max times user can retry account ID

# --- FSM States ---
class State:
    GREETING = "GREETING"
    AWAITING_ACCOUNT_ID = "AWAITING_ACCOUNT_ID"
    ACCOUNT_LOOKUP = "ACCOUNT_LOOKUP"
    AWAITING_NAME = "AWAITING_NAME"
    AWAITING_SECONDARY_FACTOR = "AWAITING_SECONDARY_FACTOR"
    VERIFIED = "VERIFIED"
    AWAITING_PAYMENT_AMOUNT = "AWAITING_PAYMENT_AMOUNT"
    AWAITING_CARD_DETAILS = "AWAITING_CARD_DETAILS"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    PROCESSING_PAYMENT = "PROCESSING_PAYMENT"
    COMPLETED = "COMPLETED"
    LOCKED_OUT = "LOCKED_OUT"

# --- API Error Code → User Message Mapping ---
API_ERROR_MESSAGES = {
    "account_not_found": "I couldn't find an account with that ID. Could you double-check and provide it again?",
    "invalid_amount": "The payment amount isn't valid. Please enter a positive amount with at most two decimal places that doesn't exceed your balance.",
    "insufficient_balance": "That amount exceeds your outstanding balance. Please enter a smaller amount.",
    "invalid_card": "The card number doesn't appear to be valid. Please check and re-enter the full card number.",
    "invalid_cvv": "The CVV you entered is incorrect. It should be 3 digits (or 4 digits for American Express cards).",
    "invalid_expiry": "The expiry date is invalid or the card has already expired. Please check and try again.",
}

# --- Gemini ---
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_TEMPERATURE = 0.0  # Deterministic extraction
