"""
agent/agent.py
--------------
LLM orchestration / agentic reasoning layer.

TODO: Implement multi-step reasoning, tool-calling, and memory management.
      Suggested libraries: openai, langchain, or google-generativeai.
"""

from app.config import settings


class RecoupAgent:
    """
    Stub agent.  Wire in a real LLM client once API keys are configured.

    Usage (future):
        agent = RecoupAgent()
        response = await agent.run(task="Should we retry payment pay_xxx?", context=...)
    """

    def __init__(self) -> None:
        # TODO: Initialise the LLM client using settings.openai_api_key
        self.model = settings.openai_model

    async def run(self, task: str, context: dict | None = None) -> str:
        """Execute an agentic task and return the final answer.  Not yet implemented."""
        # TODO: build prompt → call LLM → parse tool calls → return answer
        raise NotImplementedError("RecoupAgent.run() is not yet implemented.")
