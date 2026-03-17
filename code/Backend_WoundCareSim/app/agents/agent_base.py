from abc import ABC
import logging
from openai import AsyncOpenAI

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all evaluator agents.
    Uses the OpenAI Responses API (client.responses.create).
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_CHAT_MODEL

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Executes an OpenAI Responses API call and safely extracts text.
        Handles model compatibility (GPT-5 models do not support temperature).
        """

        try:
            # -------------------------------
            # Build request parameters safely
            # -------------------------------
            request_params = {
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
            }

            # GPT-5 models do NOT support temperature
            if not self.model.startswith("gpt-5"):
                request_params["temperature"] = temperature

            # -------------------------------
            # Execute OpenAI call
            # -------------------------------
            response = await self.client.responses.create(**request_params)

            # -------------------------------
            # Parse response text safely
            # -------------------------------
            output_text = ""

            if hasattr(response, "output"):
                for item in response.output:
                    # We are looking for message outputs
                    if getattr(item, "type", None) == "message":
                        if hasattr(item, "content"):
                            for content_part in item.content:
                                c_type = getattr(content_part, "type", "")

                                if c_type in ["text", "output_text"]:
                                    text_val = getattr(content_part, "text", "")
                                    if text_val:
                                        output_text += text_val

            output_text = output_text.strip()

            if not output_text:
                logger.error(f"Raw Response Output: {response.output}")
                raise ValueError("OpenAI returned empty content after parsing.")

            return output_text

        except Exception as e:
            logger.error(f"LLM Responses API Call Failed: {e}")

            # Return empty JSON string so agents do not crash
            return "{}"
