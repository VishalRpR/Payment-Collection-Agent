"""
HTTP client for the Payment Verification API.

Handles both /api/lookup-account and /api/process-payment endpoints.
All network errors are caught and returned as structured error dicts.
"""
from __future__ import annotations

import requests
from config import API_BASE_URL, LOOKUP_ENDPOINT, PAYMENT_ENDPOINT, API_TIMEOUT_SECONDS


class PaymentAPI:
    """Client for the payment verification API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ──────────────────────────────────────────────
    # Account Lookup
    # ──────────────────────────────────────────────

    def lookup_account(self, account_id: str) -> dict:
        """
        POST /api/lookup-account
        
        Returns:
            On success: {"success": True, "data": {account_id, full_name, dob, ...}}
            On failure: {"success": False, "error_code": str, "message": str}
        """
        url = f"{self.base_url}{LOOKUP_ENDPOINT}"
        payload = {"account_id": account_id}

        try:
            response = self.session.post(url, json=payload, timeout=API_TIMEOUT_SECONDS)

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 404:
                body = response.json()
                return {
                    "success": False,
                    "error_code": body.get("error_code", "account_not_found"),
                    "message": body.get("message", "Account not found."),
                }
            else:
                return {
                    "success": False,
                    "error_code": "unexpected_error",
                    "message": f"Unexpected API response (status {response.status_code}).",
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error_code": "timeout",
                "message": "The request timed out. Please try again.",
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error_code": "connection_error",
                "message": "Unable to connect to the payment server. Please try again later.",
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "unknown_error",
                "message": f"An unexpected error occurred: {str(e)}",
            }

    # ──────────────────────────────────────────────
    # Process Payment
    # ──────────────────────────────────────────────

    def process_payment(
        self,
        account_id: str,
        amount: float,
        cardholder_name: str,
        card_number: str,
        cvv: str,
        expiry_month: int,
        expiry_year: int,
    ) -> dict:
        """
        POST /api/process-payment
        
        Returns:
            On success: {"success": True, "transaction_id": str}
            On failure: {"success": False, "error_code": str}
        """
        url = f"{self.base_url}{PAYMENT_ENDPOINT}"
        payload = {
            "account_id": account_id,
            "amount": amount,
            "payment_method": {
                "type": "card",
                "card": {
                    "cardholder_name": cardholder_name,
                    "card_number": card_number,
                    "cvv": cvv,
                    "expiry_month": expiry_month,
                    "expiry_year": expiry_year,
                },
            },
        }

        try:
            response = self.session.post(url, json=payload, timeout=API_TIMEOUT_SECONDS)

            if response.status_code == 200:
                body = response.json()
                if body.get("success"):
                    return {
                        "success": True,
                        "transaction_id": body.get("transaction_id"),
                    }
                else:
                    return {
                        "success": False,
                        "error_code": body.get("error_code", "unknown_error"),
                    }
            elif response.status_code == 422:
                body = response.json()
                return {
                    "success": False,
                    "error_code": body.get("error_code", "unknown_error"),
                }
            else:
                return {
                    "success": False,
                    "error_code": "unexpected_error",
                    "message": f"Unexpected API response (status {response.status_code}).",
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error_code": "timeout",
                "message": "The payment request timed out. Please try again.",
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error_code": "connection_error",
                "message": "Unable to connect to the payment server. Please try again later.",
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "unknown_error",
                "message": f"An unexpected error occurred: {str(e)}",
            }
