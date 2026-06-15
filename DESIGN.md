# Design Document — Payment Collection AI Agent

## Architecture Overview

The agent uses a **hybrid architecture**: an LLM for natural language understanding combined with a deterministic finite state machine (FSM) for flow control and validation.

```
User Input → LLM Parser → State Machine → Validators/API → Response
                ↑                              ↓
         (Gemini 2.5 Flash)          (Deterministic Python)
```

### Why Hybrid?

The assignment presents a fundamental tension:
- **Users type messy, conversational input** ("I was born on 14th May 1990") — requires NLU
- **Verification must be strict** (exact name matching, no fuzzy logic) — requires determinism
- **Flow must never skip steps** — requires a strict state machine

A pure state machine with regex would break on natural language. A pure LLM approach would risk skipping steps or hallucinating verification results. The hybrid approach uses each where they're strongest:

| Concern | Approach | Rationale |
|---|---|---|
| Parsing user input | LLM (Gemini 2.5 Flash) | Handles "14th May 1990", "one two three", card numbers with spaces |
| Flow control | Deterministic FSM | Never skips steps, enforces ordering |
| Verification | Deterministic Python | Exact string match — no LLM involvement in security-critical decisions |
| Input validation | Deterministic Python | Luhn check, date parsing, CVV rules |
| Response generation | Template-based | Predictable, no hallucination risk |

### Module Structure

| Module | Responsibility |
|---|---|
| `agent.py` | Entry point — `Agent.next()` interface |
| `state_machine.py` | FSM with 11 states, transitions, and handler logic |
| `conversation.py` | Stateful context management across turns |
| `parsers.py` | LLM-based structured extraction from free-form text |
| `validators.py` | Deterministic validation (Luhn, dates, amounts, etc.) |
| `api_client.py` | HTTP client for lookup + payment APIs |
| `config.py` | Constants, state names, error mappings |

## Key Decisions

### 1. Verification: Name Matching is Case-Sensitive

The spec says *"no case-insensitive workarounds for names."* I interpret this literally: `"Nithin Jain" ≠ "nithin jain"`. The LLM parser is instructed to preserve exact casing from user input. This means if the user types their name in lowercase, verification fails — which is strict but spec-compliant.

### 2. Retry Policy: 3 Total Attempts

I chose 3 total verification attempts (across name + secondary factor), consistent with banking industry standards. This means a user who gets their name wrong once has 2 attempts left for the secondary factor.

### 3. Confirmation Step Before Payment

I added an explicit confirmation step ("Pay ₹500 with card ending 0366?") before calling the payment API. This adds one turn but prevents accidental payments — standard UX in financial applications.

### 4. Card Data Lifecycle

Card data is:
1. Collected from user input
2. Validated client-side (Luhn, CVV, expiry)
3. Sent to the API
4. **Immediately wiped from memory** after the API call

The agent never echoes back full card numbers, only the last 4 digits.

### 5. LLM with Regex Fallback

If the Gemini API is unavailable (no key, network error), the parser falls back to regex-based extraction. This is less accurate for conversational input but ensures the agent still functions.

## Tradeoffs Accepted

1. **Templates over LLM for responses:** Agent responses are template-based, not LLM-generated. This sacrifices conversational flair for predictability and speed. No risk of the LLM accidentally exposing PII in a response.

2. **No persistence:** All state is in-memory. A crash loses the session. For a production system, I'd add session persistence with encryption for sensitive data.

3. **Single-factor secondary verification:** The agent accepts any ONE of DOB/Aadhaar/Pincode. A more secure system might require multiple factors.

4. **No rate limiting:** The agent doesn't implement rate limiting on API calls. In production, I'd add exponential backoff and circuit breakers.


6. **Streaming responses** — For better perceived latency when the LLM is processing.

7. **Automated regression testing** — CI pipeline running the evaluation suite on every commit, with performance benchmarks.
