"""
Interactive CLI runner for the Payment Collection Agent.

Usage:
    python main.py

Set OPENAI_API_KEY in your environment or .env file before running.
"""
from __future__ import annotations

import os
import sys

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent import Agent


def main():
    """Run the payment agent in interactive CLI mode."""
    print("=" * 60)
    print("  Payment Collection Agent — Interactive Mode")
    print("=" * 60)
    print()

    # Check for API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("[WARN] GEMINI_API_KEY not set. The agent will use regex-based")
        print("       parsing, which has limited support for conversational input.")
        print("       Set GEMINI_API_KEY for the best experience.")
        print()

    agent = Agent()

    # Initial greeting
    response = agent.next("Hi")
    print(f"Agent: {response['message']}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended by user. Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("\nSession ended. Goodbye!")
            break

        response = agent.next(user_input)
        print(f"\nAgent: {response['message']}\n")


if __name__ == "__main__":
    main()
