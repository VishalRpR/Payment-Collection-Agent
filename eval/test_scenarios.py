"""
Test scenarios for automated evaluation.

Each scenario defines a scripted conversation with expected outcomes.
Used by evaluator.py to run automated assessments.
"""

SCENARIOS = [
    # ──────────────────────────────────────────────
    # Scenario 1: Happy path — ACC1001 full payment
    # ──────────────────────────────────────────────
    {
        "name": "Happy Path — Full Payment (ACC1001)",
        "description": "Cooperative user completes full payment flow",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "My account ID is ACC1001", "expect_contains": ["name"]},
            {"input": "Nithin Jain", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "My DOB is 1990-05-14", "expect_contains": ["verified", "1,250.75", "1250.75"], "expect_any": True},
            {"input": "I want to pay 500 rupees", "expect_contains": ["card"]},
            {"input": "Card number 4532015112830366, CVV 123, expiry 12/2027, cardholder Nithin Jain", "expect_contains": ["confirm"]},
            {"input": "Yes, go ahead", "expect_contains": ["success", "transaction"], "expect_any": True},
        ],
        "expected_outcome": "payment_success",
    },

    # ──────────────────────────────────────────────
    # Scenario 2: Verification failure — wrong name
    # ──────────────────────────────────────────────
    {
        "name": "Verification Failure — Wrong Name (ACC1001)",
        "description": "User provides wrong name 3 times and gets locked out",
        "turns": [
            {"input": "Hello", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "my name is John Doe", "expect_contains": ["doesn't match", "attempt"], "expect_any": True},
            {"input": "my name is Jane Smith", "expect_contains": ["doesn't match", "attempt"], "expect_any": True},
            {"input": "my name is Random Person", "expect_contains": ["locked", "support"], "expect_any": True},
        ],
        "expected_outcome": "locked_out",
    },

    # ──────────────────────────────────────────────
    # Scenario 3: Zero balance — ACC1003
    # ──────────────────────────────────────────────
    {
        "name": "Zero Balance — No Payment Needed (ACC1003)",
        "description": "Account has ₹0 balance — agent should close gracefully",
        "turns": [
            {"input": "Hi there", "expect_contains": ["account"]},
            {"input": "ACC1003", "expect_contains": ["name"]},
            {"input": "Priya Agarwal", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "1992-08-10", "expect_contains": ["0.00", "nothing", "no outstanding"], "expect_any": True},
        ],
        "expected_outcome": "zero_balance",
    },

    # ──────────────────────────────────────────────
    # Scenario 4: Leap year DOB — ACC1004
    # ──────────────────────────────────────────────
    {
        "name": "Leap Year DOB (ACC1004)",
        "description": "Account has Feb 29 DOB — agent must handle correctly",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1004", "expect_contains": ["name"]},
            {"input": "Rahul Mehta", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "1988-02-29", "expect_contains": ["verified", "3,200.50", "3200.50"], "expect_any": True},
        ],
        "expected_outcome": "verified",
    },

    # ──────────────────────────────────────────────
    # Scenario 5: Wrong secondary factor
    # ──────────────────────────────────────────────
    {
        "name": "Wrong Secondary Factor (ACC1001)",
        "description": "Correct name but wrong DOB",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "Nithin Jain", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "1991-01-01", "expect_contains": ["doesn't match", "attempt", "try again"], "expect_any": True},
        ],
        "expected_outcome": "verification_retry",
    },

    # ──────────────────────────────────────────────
    # Scenario 6: User cancels mid-flow
    # ──────────────────────────────────────────────
    {
        "name": "Cancellation Mid-Flow",
        "description": "User cancels during verification",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "never mind, cancel", "expect_contains": ["cancel", "ended", "session"], "expect_any": True},
        ],
        "expected_outcome": "cancelled",
    },

    # ──────────────────────────────────────────────
    # Scenario 7: Account not found
    # ──────────────────────────────────────────────
    {
        "name": "Account Not Found",
        "description": "User provides non-existent account ID",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC9999", "expect_contains": ["couldn't find", "not found", "double-check"], "expect_any": True},
        ],
        "expected_outcome": "account_not_found",
    },

    # ──────────────────────────────────────────────
    # Scenario 8: Aadhaar verification (alternative factor)
    # ──────────────────────────────────────────────
    {
        "name": "Aadhaar Verification (ACC1001)",
        "description": "User verifies with Aadhaar last 4 instead of DOB",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "Nithin Jain", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "Last 4 of Aadhaar is 4321", "expect_contains": ["verified", "1,250.75", "1250.75"], "expect_any": True},
        ],
        "expected_outcome": "verified",
    },

    # ──────────────────────────────────────────────
    # Scenario 9: Full amount payment
    # ──────────────────────────────────────────────
    {
        "name": "Full Amount Payment (ACC1001)",
        "description": "User says 'pay the full amount'",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "Nithin Jain", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "1990-05-14", "expect_contains": ["verified", "1,250.75", "1250.75"], "expect_any": True},
            {"input": "Just clear the full amount", "expect_contains": ["1,250.75", "1250.75", "card"], "expect_any": True},
        ],
        "expected_outcome": "amount_accepted",
    },

    # ──────────────────────────────────────────────
    # Scenario 10: Payment declined — confirmation "No"
    # ──────────────────────────────────────────────
    {
        "name": "Payment Declined by User",
        "description": "User declines payment at confirmation step",
        "turns": [
            {"input": "Hi", "expect_contains": ["account"]},
            {"input": "ACC1001", "expect_contains": ["name"]},
            {"input": "Nithin Jain", "expect_contains": ["date of birth", "aadhaar", "pincode"], "expect_any": True},
            {"input": "1990-05-14", "expect_contains": ["verified", "balance"], "expect_any": True},
            {"input": "500", "expect_contains": ["card"]},
            {"input": "Card 4532015112830366, CVV 123, expiry 12/2027, name Nithin Jain", "expect_contains": ["confirm"]},
            {"input": "No, cancel that", "expect_contains": ["cancel", "different", "end"], "expect_any": True},
        ],
        "expected_outcome": "payment_declined",
    },
]
