"""
Finite State Machine for the Payment Collection Agent.

Controls the conversation flow with deterministic transitions.
Each state handler returns a response message and optionally transitions to the next state.
"""
from __future__ import annotations

from config import (
    State,
    MAX_VERIFICATION_ATTEMPTS,
    MAX_PAYMENT_ATTEMPTS,
    MAX_ACCOUNT_LOOKUP_ATTEMPTS,
    API_ERROR_MESSAGES,
)
from conversation import ConversationContext
from api_client import PaymentAPI
from validators import (
    validate_account_id,
    validate_name,
    validate_dob,
    validate_aadhaar_last4,
    validate_pincode,
    validate_amount,
    validate_card_details,
)
from parsers import extract


class StateMachine:
    """
    Deterministic FSM that drives the payment collection flow.
    
    Each state has a handler method that:
    1. Processes extracted user data
    2. Performs validation / API calls as needed
    3. Generates a response message
    4. Transitions to the next state (if appropriate)
    """

    def __init__(self, api: PaymentAPI | None = None):
        self.api = api or PaymentAPI()
        self._handlers = {
            State.GREETING: self._handle_greeting,
            State.AWAITING_ACCOUNT_ID: self._handle_awaiting_account_id,
            State.AWAITING_NAME: self._handle_awaiting_name,
            State.AWAITING_SECONDARY_FACTOR: self._handle_awaiting_secondary_factor,
            State.VERIFIED: self._handle_verified,
            State.AWAITING_PAYMENT_AMOUNT: self._handle_awaiting_payment_amount,
            State.AWAITING_CARD_DETAILS: self._handle_awaiting_card_details,
            State.AWAITING_CONFIRMATION: self._handle_awaiting_confirmation,
            State.PROCESSING_PAYMENT: self._handle_processing_payment,
            State.COMPLETED: self._handle_completed,
            State.LOCKED_OUT: self._handle_locked_out,
        }

    def process(self, user_input: str, ctx: ConversationContext) -> str:
        """
        Process one turn: extract data, run current state handler, return response.
        
        Args:
            user_input: Raw text from user
            ctx: Conversation context (mutated in place)
        
        Returns:
            Agent response message string
        """
        # Build context summary for the LLM parser
        context_summary = self._build_context_summary(ctx)

        # Extract structured data from free-form input
        extracted = extract(user_input, ctx.current_state, context_summary)

        # Check for cancellation at any point
        if extracted.get("cancel") and ctx.current_state not in (State.COMPLETED, State.LOCKED_OUT):
            ctx.current_state = State.COMPLETED
            return "No problem. The session has been cancelled. No payment was processed. Have a good day!"

        # Store any out-of-order data that might be useful later
        self._store_extracted_data(extracted, ctx)

        # Run the handler for the current state
        handler = self._handlers.get(ctx.current_state)
        if handler:
            return handler(extracted, ctx)
        else:
            return "I'm sorry, something went wrong. Please try again."

    def _build_context_summary(self, ctx: ConversationContext) -> str:
        """Build a brief summary of conversation state for the LLM parser."""
        parts = []
        if ctx.provided_account_id:
            parts.append(f"Account ID: {ctx.provided_account_id}")
        if ctx.name_verified:
            parts.append("Name: verified")
        if ctx.secondary_verified:
            parts.append("Identity: fully verified")
        if ctx.balance is not None:
            parts.append(f"Balance: ₹{ctx.balance:.2f}")
        if ctx.provided_amount is not None:
            parts.append(f"Payment amount: ₹{ctx.provided_amount:.2f}")
        return "; ".join(parts) if parts else "Conversation just started."

    def _store_extracted_data(self, extracted: dict, ctx: ConversationContext):
        """Store any data the user provides, even out of order."""
        # Only store account ID if we haven't looked up yet
        if extracted.get("account_id") and not ctx.provided_account_id:
            ctx.provided_account_id = extracted["account_id"]

        # Store name if provided early (but don't verify yet)
        if extracted.get("name") and not ctx.provided_name:
            ctx.provided_name = extracted["name"]

    # ──────────────────────────────────────────────
    # State Handlers
    # ──────────────────────────────────────────────

    def _handle_greeting(self, extracted: dict, ctx: ConversationContext) -> str:
        """Initial state → greet and ask for account ID."""
        ctx.current_state = State.AWAITING_ACCOUNT_ID

        # If user already provided account ID in the greeting
        if ctx.provided_account_id:
            return self._handle_awaiting_account_id(extracted, ctx)

        return (
            "Hello! Welcome to the payment collection service. "
            "I'll help you process a payment today.\n\n"
            "To get started, could you please share your account ID?"
        )

    def _handle_awaiting_account_id(self, extracted: dict, ctx: ConversationContext) -> str:
        """Collect account ID → lookup via API."""
        account_id = extracted.get("account_id") or ctx.provided_account_id

        if not account_id:
            return "I need your account ID to proceed. It should look like ACC followed by 4 digits (e.g., ACC1001). Could you provide it?"

        # Validate format
        if not validate_account_id(account_id):
            return f"'{account_id}' doesn't look like a valid account ID. It should be in the format ACC followed by 4 digits (e.g., ACC1001). Could you check and try again?"

        ctx.provided_account_id = account_id

        # Call the API
        result = self.api.lookup_account(account_id)

        if result["success"]:
            ctx.account_data = result["data"]
            ctx.current_state = State.AWAITING_NAME

            # If user already provided their name, process it now
            if ctx.provided_name:
                return self._handle_awaiting_name(extracted, ctx)

            return f"Found your account. For security verification, could you please tell me your full name as it appears on the account?"
        else:
            ctx.account_lookup_attempts += 1
            error_code = result.get("error_code", "unknown_error")

            if ctx.account_lookup_attempts >= MAX_ACCOUNT_LOOKUP_ATTEMPTS:
                ctx.current_state = State.LOCKED_OUT
                return "I'm sorry, I wasn't able to locate a valid account after multiple attempts. For further assistance, please contact our customer support team."

            # Reset for next attempt
            ctx.provided_account_id = None

            msg = API_ERROR_MESSAGES.get(error_code, result.get("message", "Something went wrong."))
            return f"{msg} (Attempt {ctx.account_lookup_attempts}/{MAX_ACCOUNT_LOOKUP_ATTEMPTS})"

    def _handle_awaiting_name(self, extracted: dict, ctx: ConversationContext) -> str:
        """Collect and verify the user's full name."""
        name = extracted.get("name") or ctx.provided_name

        if not name:
            return "Could you please tell me your full name as it appears on the account?"

        ctx.provided_name = name

        # Strict name match
        expected_name = ctx.account_data["full_name"]
        if validate_name(name, expected_name):
            ctx.name_verified = True
            ctx.current_state = State.AWAITING_SECONDARY_FACTOR

            # Check if any secondary factor was already provided
            if self._try_secondary_verification(extracted, ctx):
                return self._on_verification_success(ctx)

            return (
                "Thank you. For additional verification, I'll need one more piece of information. "
                "Could you please provide any one of the following:\n"
                "• Your date of birth\n"
                "• Last 4 digits of your Aadhaar number\n"
                "• Your registered pincode"
            )
        else:
            ctx.verification_attempts += 1
            remaining = MAX_VERIFICATION_ATTEMPTS - ctx.verification_attempts

            if remaining <= 0:
                ctx.current_state = State.LOCKED_OUT
                return (
                    "I'm sorry, the name you provided doesn't match our records, and you've exhausted "
                    "all verification attempts. For your security, this session has been locked. "
                    "Please contact our customer support for assistance."
                )

            ctx.provided_name = None  # Reset for retry
            return (
                f"I'm sorry, that name doesn't match what we have on file. "
                f"Please provide your full name exactly as it's registered on the account. "
                f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
            )

    def _handle_awaiting_secondary_factor(self, extracted: dict, ctx: ConversationContext) -> str:
        """Collect and verify a secondary identity factor (DOB / Aadhaar / Pincode)."""
        if self._try_secondary_verification(extracted, ctx):
            return self._on_verification_success(ctx)

        # Nothing matched — check if they provided something that was wrong
        provided_something = any([
            extracted.get("dob"),
            extracted.get("aadhaar_last4"),
            extracted.get("pincode"),
        ])

        if provided_something:
            ctx.verification_attempts += 1
            remaining = MAX_VERIFICATION_ATTEMPTS - ctx.verification_attempts

            if remaining <= 0:
                ctx.current_state = State.LOCKED_OUT
                return (
                    "I'm sorry, the information you provided doesn't match our records, and you've "
                    "exhausted all verification attempts. For your security, this session has been locked. "
                    "Please contact our customer support for assistance."
                )

            return (
                f"That doesn't match what we have on file. "
                f"Please try again with one of the following:\n"
                f"• Your date of birth\n"
                f"• Last 4 digits of your Aadhaar number\n"
                f"• Your registered pincode\n\n"
                f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
            )
        else:
            return (
                "I need one of the following to verify your identity:\n"
                "• Your date of birth\n"
                "• Last 4 digits of your Aadhaar number\n"
                "• Your registered pincode\n\n"
                "Please provide any one of these."
            )

    def _try_secondary_verification(self, extracted: dict, ctx: ConversationContext) -> bool:
        """
        Attempt to verify a secondary factor from extracted data.
        Returns True if verification passed.
        """
        account = ctx.account_data

        # Try DOB
        if extracted.get("dob"):
            ctx.provided_dob = extracted["dob"]
            if validate_dob(extracted["dob"], account["dob"]):
                ctx.secondary_verified = True
                return True

        # Try Aadhaar last 4
        if extracted.get("aadhaar_last4"):
            ctx.provided_aadhaar_last4 = extracted["aadhaar_last4"]
            if validate_aadhaar_last4(extracted["aadhaar_last4"], account["aadhaar_last4"]):
                ctx.secondary_verified = True
                return True

        # Try Pincode
        if extracted.get("pincode"):
            ctx.provided_pincode = extracted["pincode"]
            if validate_pincode(extracted["pincode"], account["pincode"]):
                ctx.secondary_verified = True
                return True

        return False

    def _on_verification_success(self, ctx: ConversationContext) -> str:
        """Handle successful verification — show balance, transition to payment."""
        balance = ctx.balance
        ctx.current_state = State.VERIFIED

        if balance is not None and balance <= 0:
            ctx.current_state = State.COMPLETED
            return (
                "Your identity has been verified successfully! ✓\n\n"
                "Your account currently has no outstanding balance (₹0.00). "
                "There's nothing to pay at this time. Thank you and have a great day!"
            )

        # Auto-transition to payment amount
        ctx.current_state = State.AWAITING_PAYMENT_AMOUNT
        return (
            f"Your identity has been verified successfully! ✓\n\n"
            f"Your outstanding balance is **₹{balance:,.2f}**.\n\n"
            f"How much would you like to pay today? You can pay any amount up to the full balance."
        )

    def _handle_verified(self, extracted: dict, ctx: ConversationContext) -> str:
        """Transitional state — show balance and move to payment."""
        # This should auto-transition, but handle if it gets here
        ctx.current_state = State.AWAITING_PAYMENT_AMOUNT
        return self._handle_awaiting_payment_amount(extracted, ctx)

    def _handle_awaiting_payment_amount(self, extracted: dict, ctx: ConversationContext) -> str:
        """Collect payment amount."""
        amount = extracted.get("amount")

        # Handle "full amount" intent
        if extracted.get("full_amount") and ctx.balance:
            amount = ctx.balance

        if amount is None:
            return (
                f"Please enter the amount you'd like to pay. "
                f"Your outstanding balance is ₹{ctx.balance:,.2f}."
            )

        # Validate amount
        is_valid, error = validate_amount(amount, ctx.balance)
        if not is_valid:
            return f"{error} Please enter a valid amount."

        ctx.provided_amount = amount
        ctx.current_state = State.AWAITING_CARD_DETAILS

        return (
            f"Great, you'd like to pay **₹{amount:,.2f}**.\n\n"
            f"Please provide your card details:\n"
            f"• Card number\n"
            f"• CVV\n"
            f"• Expiry date (month/year)\n"
            f"• Name on the card\n\n"
            f"You can provide them all at once or one at a time."
        )

    def _handle_awaiting_card_details(self, extracted: dict, ctx: ConversationContext) -> str:
        """Collect card details — can be provided all at once or incrementally."""
        card = ctx.provided_card

        # Update card fields from extracted data
        if extracted.get("card_number"):
            card.card_number = extracted["card_number"]
        if extracted.get("cvv"):
            card.cvv = extracted["cvv"]
        if extracted.get("expiry_month") is not None:
            card.expiry_month = extracted["expiry_month"]
        if extracted.get("expiry_year") is not None:
            card.expiry_year = extracted["expiry_year"]
        if extracted.get("cardholder_name"):
            card.cardholder_name = extracted["cardholder_name"]

        # Check if we have all fields
        if not card.is_complete():
            missing = card.missing_fields()
            missing_str = ", ".join(missing)
            return f"I still need the following card details: **{missing_str}**. Please provide them."

        # Client-side validation before API call
        is_valid, errors = validate_card_details(
            card.card_number, card.cvv, card.expiry_month, card.expiry_year
        )
        if not is_valid:
            error_str = " ".join(errors)
            # Reset invalid fields so user can re-enter
            if any("card number" in e.lower() for e in errors):
                card.card_number = None
            if any("cvv" in e.lower() for e in errors):
                card.cvv = None
            if any("expir" in e.lower() for e in errors):
                card.expiry_month = None
                card.expiry_year = None
            return f"There's an issue with your card details: {error_str} Please correct and re-enter."

        # Move to confirmation
        ctx.current_state = State.AWAITING_CONFIRMATION
        return (
            f"Please confirm the following payment:\n\n"
            f"• **Amount:** ₹{ctx.provided_amount:,.2f}\n"
            f"• **Card:** ending in {card.masked_number()}\n"
            f"• **Cardholder:** {card.cardholder_name}\n\n"
            f"Shall I go ahead and process this payment? (Yes/No)"
        )

    def _handle_awaiting_confirmation(self, extracted: dict, ctx: ConversationContext) -> str:
        """User confirms or cancels the payment."""
        confirmation = extracted.get("confirmation")

        if confirmation is True:
            ctx.current_state = State.PROCESSING_PAYMENT
            return self._handle_processing_payment(extracted, ctx)
        elif confirmation is False:
            # User declined — go back to payment amount
            ctx.current_state = State.AWAITING_PAYMENT_AMOUNT
            ctx.provided_amount = None
            ctx.provided_card.clear()
            return (
                "Payment cancelled. Would you like to try with different payment details, "
                "or would you like to end this session?"
            )
        else:
            return "I need a clear yes or no. Shall I process this payment?"

    def _handle_processing_payment(self, extracted: dict, ctx: ConversationContext) -> str:
        """Call the payment API and handle the result."""
        card = ctx.provided_card

        result = self.api.process_payment(
            account_id=ctx.provided_account_id,
            amount=ctx.provided_amount,
            cardholder_name=card.cardholder_name,
            card_number=card.card_number,
            cvv=card.cvv,
            expiry_month=card.expiry_month,
            expiry_year=card.expiry_year,
        )

        # SECURITY: Clear card data after API call
        ctx.clear_card_data()

        if result["success"]:
            ctx.transaction_id = result["transaction_id"]
            ctx.current_state = State.COMPLETED

            return (
                f"✅ **Payment successful!**\n\n"
                f"• **Transaction ID:** {ctx.transaction_id}\n"
                f"• **Amount paid:** ₹{ctx.provided_amount:,.2f}\n"
                f"• **Account:** {ctx.provided_account_id}\n\n"
                f"Your payment has been processed successfully. "
                f"Please save your transaction ID for your records.\n\n"
                f"Is there anything else I can help you with, or shall we wrap up?"
            )
        else:
            error_code = result.get("error_code", "unknown_error")
            ctx.payment_attempts += 1

            if ctx.payment_attempts >= MAX_PAYMENT_ATTEMPTS:
                ctx.current_state = State.COMPLETED
                return (
                    f"I'm sorry, the payment could not be processed after {MAX_PAYMENT_ATTEMPTS} attempts. "
                    f"Please try again later or contact customer support for assistance. "
                    f"No charges have been applied to your card."
                )

            # Map error code to user-friendly message
            error_msg = API_ERROR_MESSAGES.get(
                error_code,
                result.get("message", "The payment could not be processed."),
            )

            remaining = MAX_PAYMENT_ATTEMPTS - ctx.payment_attempts

            # Determine which fields to reset based on error
            if error_code in ("invalid_card", "invalid_cvv", "invalid_expiry"):
                ctx.current_state = State.AWAITING_CARD_DETAILS
                return (
                    f"{error_msg}\n\n"
                    f"Please provide corrected card details. "
                    f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
                )
            elif error_code == "insufficient_balance":
                ctx.current_state = State.AWAITING_PAYMENT_AMOUNT
                ctx.provided_amount = None
                return (
                    f"{error_msg}\n\n"
                    f"Please enter a different amount. "
                    f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
                )
            elif error_code == "invalid_amount":
                ctx.current_state = State.AWAITING_PAYMENT_AMOUNT
                ctx.provided_amount = None
                return (
                    f"{error_msg}\n\n"
                    f"Please enter a valid payment amount. "
                    f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
                )
            else:
                ctx.current_state = State.AWAITING_CARD_DETAILS
                return (
                    f"{error_msg}\n\n"
                    f"Would you like to try again? "
                    f"({remaining} attempt{'s' if remaining > 1 else ''} remaining)"
                )

    def _handle_completed(self, extracted: dict, ctx: ConversationContext) -> str:
        """Conversation is complete — respond to follow-up messages."""
        if ctx.transaction_id:
            return (
                f"Your payment of ₹{ctx.provided_amount:,.2f} was successfully processed "
                f"(Transaction ID: {ctx.transaction_id}). "
                f"Thank you for using our payment service. Goodbye!"
            )
        else:
            return "This session has ended. Thank you for using our payment service. Goodbye!"

    def _handle_locked_out(self, extracted: dict, ctx: ConversationContext) -> str:
        """User is locked out due to failed verification — no further action."""
        return (
            "This session has been locked due to failed verification attempts. "
            "For your security, no further actions can be taken. "
            "Please contact our customer support team for assistance."
        )
