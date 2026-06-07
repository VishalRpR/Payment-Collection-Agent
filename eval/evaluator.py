"""
Automated evaluation runner for the Payment Collection Agent.

Runs test scenarios against the agent, checks assertions, and reports results.
Can run with live API or mocked API.

Usage:
    python eval/evaluator.py              # Run with live API
    python eval/evaluator.py --mock       # Run with mocked API
"""
from __future__ import annotations

import sys
import os
import re
import json
import argparse
from datetime import datetime
from unittest.mock import patch, MagicMock

# Fix Windows console encoding for emoji
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Force regex mode for reproducible evaluation
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")

from agent import Agent
from eval.test_scenarios import SCENARIOS


# ──────────────────────────────────────────────
# Mock API data
# ──────────────────────────────────────────────

MOCK_ACCOUNTS = {
    "ACC1001": {
        "success": True,
        "data": {
            "account_id": "ACC1001",
            "full_name": "Nithin Jain",
            "dob": "1990-05-14",
            "aadhaar_last4": "4321",
            "pincode": "400001",
            "balance": 1250.75,
        },
    },
    "ACC1002": {
        "success": True,
        "data": {
            "account_id": "ACC1002",
            "full_name": "Rajarajeswari Balasubramaniam",
            "dob": "1985-11-23",
            "aadhaar_last4": "9876",
            "pincode": "400002",
            "balance": 540.00,
        },
    },
    "ACC1003": {
        "success": True,
        "data": {
            "account_id": "ACC1003",
            "full_name": "Priya Agarwal",
            "dob": "1992-08-10",
            "aadhaar_last4": "2468",
            "pincode": "400003",
            "balance": 0.00,
        },
    },
    "ACC1004": {
        "success": True,
        "data": {
            "account_id": "ACC1004",
            "full_name": "Rahul Mehta",
            "dob": "1988-02-29",
            "aadhaar_last4": "1357",
            "pincode": "400004",
            "balance": 3200.50,
        },
    },
}

MOCK_NOT_FOUND = {
    "success": False,
    "error_code": "account_not_found",
    "message": "No account found with the provided account_id.",
}

MOCK_PAYMENT_SUCCESS = {
    "success": True,
    "transaction_id": "txn_eval_test_12345",
}


# ──────────────────────────────────────────────
# PII Leakage Checker
# ──────────────────────────────────────────────

# Sensitive data patterns that should NEVER appear in agent responses
PII_PATTERNS = [
    (r"\b\d{4}-\d{2}-\d{2}\b", "DOB pattern (YYYY-MM-DD)"),  # DOB
    (r"\b\d{12}\b", "Full Aadhaar number"),                     # Full Aadhaar
    # Note: We do NOT flag 4-digit sequences (too many false positives)
    # or 6-digit sequences (agent may legitimately mention amounts)
]


def check_pii_leakage(response: str, account_data: dict | None) -> list[str]:
    """Check if the agent response leaks any PII from account data."""
    leaks = []
    if not account_data:
        return leaks

    data = account_data.get("data", account_data)

    # Check if DOB appears in response (after verification)
    dob = data.get("dob", "")
    if dob and dob in response:
        leaks.append(f"DOB '{dob}' found in response")

    # Check if Aadhaar last 4 appears in a context that looks like exposure
    aadhaar = data.get("aadhaar_last4", "")
    if aadhaar and f"aadhaar" in response.lower() and aadhaar in response:
        leaks.append(f"Aadhaar last 4 '{aadhaar}' exposed in response")

    # Check pincode exposure
    pincode = data.get("pincode", "")
    if pincode and "pincode" in response.lower() and pincode in response:
        leaks.append(f"Pincode '{pincode}' exposed in response")

    return leaks


# ──────────────────────────────────────────────
# Evaluation Runner
# ──────────────────────────────────────────────

def run_scenario(scenario: dict, use_mock: bool = True) -> dict:
    """
    Run a single test scenario and collect results.
    
    Returns:
        {
            "name": str,
            "passed": bool,
            "turns": [{input, response, checks_passed, checks_failed, pii_leaks}],
            "total_checks": int,
            "passed_checks": int,
            "failed_checks": int,
            "pii_leaks": [str],
        }
    """
    result = {
        "name": scenario["name"],
        "passed": True,
        "turns": [],
        "total_checks": 0,
        "passed_checks": 0,
        "failed_checks": 0,
        "pii_leaks": [],
    }

    if use_mock:
        agent = Agent()

        # Mock the API
        def mock_lookup(account_id):
            return MOCK_ACCOUNTS.get(account_id, MOCK_NOT_FOUND)

        def mock_payment(*args, **kwargs):
            return MOCK_PAYMENT_SUCCESS

        agent.state_machine.api.lookup_account = mock_lookup
        agent.state_machine.api.process_payment = mock_payment
    else:
        agent = Agent()

    for i, turn in enumerate(scenario["turns"]):
        user_input = turn["input"]
        response = agent.next(user_input)
        msg = response["message"].lower()

        turn_result = {
            "input": user_input,
            "response": response["message"],
            "checks_passed": [],
            "checks_failed": [],
            "pii_leaks": [],
        }

        # Check expected content
        expect_contains = turn.get("expect_contains", [])
        expect_any = turn.get("expect_any", False)

        if expect_contains:
            if expect_any:
                # At least one of the expected strings must be present
                found_any = False
                for expected in expect_contains:
                    if expected.lower() in msg:
                        found_any = True
                        turn_result["checks_passed"].append(f"Contains '{expected}'")
                        break

                result["total_checks"] += 1
                if found_any:
                    result["passed_checks"] += 1
                else:
                    result["failed_checks"] += 1
                    result["passed"] = False
                    turn_result["checks_failed"].append(
                        f"Expected any of {expect_contains}, got: {response['message'][:100]}..."
                    )
            else:
                # ALL expected strings must be present
                for expected in expect_contains:
                    result["total_checks"] += 1
                    if expected.lower() in msg:
                        result["passed_checks"] += 1
                        turn_result["checks_passed"].append(f"Contains '{expected}'")
                    else:
                        result["failed_checks"] += 1
                        result["passed"] = False
                        turn_result["checks_failed"].append(
                            f"Expected '{expected}' in response"
                        )

        # PII leakage check
        if use_mock and agent.context.account_data:
            leaks = check_pii_leakage(response["message"], agent.context.account_data)
            turn_result["pii_leaks"] = leaks
            result["pii_leaks"].extend(leaks)

        result["turns"].append(turn_result)

    return result


def run_all(use_mock: bool = True) -> list[dict]:
    """Run all scenarios and return results."""
    results = []
    for scenario in SCENARIOS:
        result = run_scenario(scenario, use_mock=use_mock)
        results.append(result)
    return results


def print_report(results: list[dict]):
    """Print a formatted evaluation report."""
    print("=" * 70)
    print("  PAYMENT AGENT — EVALUATION REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    total_scenarios = len(results)
    passed_scenarios = sum(1 for r in results if r["passed"])
    total_checks = sum(r["total_checks"] for r in results)
    passed_checks = sum(r["passed_checks"] for r in results)
    total_leaks = sum(len(r["pii_leaks"]) for r in results)

    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  {status}  {r['name']}")
        print(f"         Checks: {r['passed_checks']}/{r['total_checks']}")

        if r["pii_leaks"]:
            print(f"         ⚠️  PII Leaks: {r['pii_leaks']}")

        for turn in r["turns"]:
            if turn["checks_failed"]:
                for fail in turn["checks_failed"]:
                    print(f"         ✗ {fail}")
        print()

    print("-" * 70)
    print(f"  SUMMARY")
    print(f"  Scenarios: {passed_scenarios}/{total_scenarios} passed")
    print(f"  Checks:    {passed_checks}/{total_checks} passed")
    print(f"  PII Leaks: {total_leaks}")
    print(f"  Success Rate: {passed_checks/total_checks*100:.1f}%" if total_checks else "  No checks run")
    print("=" * 70)


def save_report(results: list[dict], filepath: str):
    """Save a markdown report to file."""
    lines = [
        "# Payment Agent — Evaluation Results\n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "",
    ]

    total_scenarios = len(results)
    passed_scenarios = sum(1 for r in results if r["passed"])
    total_checks = sum(r["total_checks"] for r in results)
    passed_checks = sum(r["passed_checks"] for r in results)

    lines.append(f"## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Scenarios passed | {passed_scenarios}/{total_scenarios} |")
    lines.append(f"| Checks passed | {passed_checks}/{total_checks} |")
    lines.append(f"| Success rate | {passed_checks/total_checks*100:.1f}% |" if total_checks else "| Success rate | N/A |")
    lines.append(f"| PII leaks | {sum(len(r['pii_leaks']) for r in results)} |")
    lines.append("")

    lines.append(f"## Detailed Results\n")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        lines.append(f"### {status} {r['name']}\n")
        lines.append(f"**Checks:** {r['passed_checks']}/{r['total_checks']}\n")

        if r["pii_leaks"]:
            lines.append(f"> [!WARNING]")
            lines.append(f"> PII Leaks detected: {', '.join(r['pii_leaks'])}\n")

        lines.append(f"| Turn | Input | Result |")
        lines.append(f"|---|---|---|")
        for i, turn in enumerate(r["turns"]):
            passed_str = ", ".join(turn["checks_passed"]) if turn["checks_passed"] else ""
            failed_str = ", ".join(turn["checks_failed"]) if turn["checks_failed"] else ""
            status_emoji = "✅" if not turn["checks_failed"] else "❌"
            detail = failed_str if failed_str else passed_str
            lines.append(f"| {i+1} | `{turn['input'][:50]}` | {status_emoji} {detail[:80]} |")
        lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nReport saved to: {filepath}")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Payment Agent Evaluator")
    parser.add_argument("--mock", action="store_true", help="Use mocked API (default: live API)")
    parser.add_argument("--save", type=str, default=None, help="Save report to file")
    args = parser.parse_args()

    results = run_all(use_mock=args.mock or True)  # Default to mock
    print_report(results)

    save_path = args.save or os.path.join(os.path.dirname(__file__), "eval_results.md")
    save_report(results, save_path)
