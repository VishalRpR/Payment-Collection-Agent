"""Quick test: run a full happy-path conversation and print each turn."""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")

# Load .env
from dotenv import load_dotenv
load_dotenv()

from agent import Agent

agent = Agent()

conversation = [
    "Hi there!",
    "My account ID is ACC1001",
    "My name is Nithin Jain",
    "My date of birth is 1990-05-14",
    "I'd like to pay 500 rupees",
    "Card number 4532015112830366, CVV 123, expiry 12/2027, cardholder Nithin Jain",
    "Yes, go ahead",
]

print("=" * 60)
print("  HAPPY PATH TEST — ACC1001")
print("=" * 60)

for user_msg in conversation:
    print(f"\n👤 User: {user_msg}")
    response = agent.next(user_msg)
    print(f"🤖 Agent: {response['message']}")
    print("-" * 60)

print("\n\n")

# Test 2: Zero balance
print("=" * 60)
print("  ZERO BALANCE TEST — ACC1003")
print("=" * 60)

agent2 = Agent()
conversation2 = [
    "Hello",
    "ACC1003",
    "Priya Agarwal",
    "1992-08-10",
]

for user_msg in conversation2:
    print(f"\n👤 User: {user_msg}")
    response = agent2.next(user_msg)
    print(f"🤖 Agent: {response['message']}")
    print("-" * 60)

print("\n\n")

# Test 3: Verification failure
print("=" * 60)
print("  VERIFICATION LOCKOUT TEST — ACC1001")
print("=" * 60)

agent3 = Agent()
conversation3 = [
    "Hi",
    "ACC1001",
    "John Doe",
    "Jane Smith",
    "Random Person",
    "Nithin Jain",  # Too late — locked out
]

for user_msg in conversation3:
    print(f"\n👤 User: {user_msg}")
    response = agent3.next(user_msg)
    print(f"🤖 Agent: {response['message']}")
    print("-" * 60)
