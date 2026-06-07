"""
Payment Collection AI Agent.

Exposes the required interface for automated evaluation:

    agent = Agent()
    result = agent.next("Hi")
    # → {"message": "Hello! Welcome to the payment collection service..."}

All state is maintained internally between calls to next().
"""
from __future__ import annotations

from conversation import ConversationContext
from state_machine import StateMachine
from api_client import PaymentAPI


class Agent:
    """
    Conversational AI agent for payment collection.
    
    Maintains full conversation state internally between calls.
    Each call to next() represents exactly one turn.
    """

    def __init__(self):
        self.context = ConversationContext()
        self.api = PaymentAPI()
        self.state_machine = StateMachine(api=self.api)
        self._first_turn = True

    def next(self, user_input: str) -> dict:
        """
        Process one turn of the conversation.

        Args:
            user_input: The user's message as a plain string.

        Returns:
            {
                "message": str   # The agent's response to display to the user
            }
        """
        # Record user message in conversation history
        self.context.add_user_message(user_input)

        # Process through state machine
        response = self.state_machine.process(user_input, self.context)

        # Record agent response in conversation history
        self.context.add_agent_message(response)

        return {"message": response}
