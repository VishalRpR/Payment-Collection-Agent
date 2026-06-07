# Payment Collection AI Agent

A conversational AI agent that handles end-to-end payment collection: account lookup → identity verification → card payment → outcome communication.

## Quick Start

### Prerequisites
- Python 3.10+
- Gemini API key (for best results)

### Setup

```bash
cd payment-agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
# Edit .env and add your key:
#   GEMINI_API_KEY=AIzaSy...
```

### Run Interactively

```bash
python main.py
```

### Run Tests

```bash
pytest tests/ -v
```

### Run Evaluation

```bash
python eval/evaluator.py --mock
```

## Architecture

```
User Input → LLM Parser (Gemini 2.5 Flash) → Deterministic State Machine → API → Response
```

- **LLM** handles parsing messy input ("born on 14th May 1990" → structured data)
- **State Machine** controls flow (never skips steps)
- **Validators** handle verification and card checks (pure Python, no LLM)

See [DESIGN.md](DESIGN.md) for the full architecture document.

## Agent Interface

```python
from agent import Agent

agent = Agent()
result = agent.next("Hi")
print(result["message"])  # "Hello! Welcome to the payment collection service..."
```

## Project Structure

```
payment-agent/
├── agent.py              # Main Agent class (next() interface)
├── state_machine.py      # FSM: 11 states, transitions, handlers
├── conversation.py       # Conversation context management
├── parsers.py            # LLM + regex input extraction
├── validators.py         # Deterministic validation (Luhn, dates, etc.)
├── api_client.py         # HTTP client for lookup + payment APIs
├── config.py             # Constants and configuration
├── main.py               # Interactive CLI runner
├── DESIGN.md             # Architecture & design decisions
├── requirements.txt
├── tests/
│   ├── test_validators.py    # Unit tests for validators
│   └── test_agent_e2e.py     # End-to-end conversation tests
└── eval/
    ├── evaluator.py          # Automated evaluation runner
    ├── test_scenarios.py     # 10 test scenarios
    └── eval_results.md       # Generated results
```

---

## Sample Conversations

### 1. Successful End-to-End Payment (ACC1001)

```
Agent: Hello! Welcome to the payment collection service. I'll help you process
       a payment today. To get started, could you please share your account ID?

User:  My account ID is ACC1001

Agent: Found your account. For security verification, could you please tell me
       your full name as it appears on the account?

User:  Nithin Jain

Agent: Thank you. For additional verification, I'll need one more piece of
       information. Could you please provide any one of the following:
       • Your date of birth
       • Last 4 digits of your Aadhaar number
       • Your registered pincode

User:  My DOB is 1990-05-14

Agent: Your identity has been verified successfully! ✓
       Your outstanding balance is ₹1,250.75.
       How much would you like to pay today?

User:  I'd like to pay 500 rupees

Agent: Great, you'd like to pay ₹500.00. Please provide your card details:
       • Card number
       • CVV
       • Expiry date (month/year)
       • Name on the card

User:  Card 4532015112830366, CVV 123, expiry 12/2027, name Nithin Jain

Agent: Please confirm the following payment:
       • Amount: ₹500.00
       • Card: ending in ****0366
       • Cardholder: Nithin Jain
       Shall I go ahead and process this payment? (Yes/No)

User:  Yes

Agent: ✅ Payment successful!
       • Transaction ID: txn_1762510325322_l1fl4oy
       • Amount paid: ₹500.00
       • Account: ACC1001
       Please save your transaction ID for your records.
```

### 2. Verification Failure — User Exhausts Retries

```
Agent: Hello! Welcome to the payment collection service. To get started,
       could you please share your account ID?

User:  ACC1001

Agent: Found your account. For security verification, could you please tell me
       your full name as it appears on the account?

User:  John Doe

Agent: I'm sorry, that name doesn't match what we have on file. Please provide
       your full name exactly as it's registered on the account. (2 attempts remaining)

User:  Jane Smith

Agent: I'm sorry, that name doesn't match what we have on file. Please provide
       your full name exactly as it's registered on the account. (1 attempt remaining)

User:  Random Person

Agent: I'm sorry, the name you provided doesn't match our records, and you've
       exhausted all verification attempts. For your security, this session has
       been locked. Please contact our customer support for assistance.
```

### 3. Payment Failure — Invalid Card

```
[After successful verification...]

User:  Card number 1234567890123456, CVV 123, expiry 12/2027, name Nithin Jain

Agent: There's an issue with your card details: Card number is not valid (failed
       checksum). Please correct and re-enter.

User:  Card 4532015112830366, CVV 123, expiry 12/2027, name Nithin Jain

Agent: Please confirm the following payment:
       • Amount: ₹500.00
       • Card: ending in ****0366
       Shall I go ahead and process this payment? (Yes/No)

User:  Yes

Agent: ✅ Payment successful!
```

### 4. Edge Case — Zero Balance (ACC1003)

```
Agent: Hello! To get started, could you please share your account ID?

User:  ACC1003

Agent: Found your account. Could you please tell me your full name?

User:  Priya Agarwal

Agent: For verification, please provide your DOB, Aadhaar last 4, or pincode.

User:  1992-08-10

Agent: Your identity has been verified successfully! ✓
       Your account currently has no outstanding balance (₹0.00). There's nothing
       to pay at this time. Thank you and have a great day!
```

### 5. Edge Case — Leap Year DOB (ACC1004)

```
User:  ACC1004

Agent: Found your account. Could you please tell me your full name?

User:  Rahul Mehta

Agent: For verification, please provide your DOB, Aadhaar last 4, or pincode.

User:  1988-02-29

Agent: Your identity has been verified successfully! ✓
       Your outstanding balance is ₹3,200.50.
```
