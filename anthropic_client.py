"""
This wraps your existing A6 AI call (Sehat Sahara chatbot logic).
Replace the body of call_anthropic() with your actual implementation
from your Sehat Sahara project — this is just the interface the worker expects.
"""
import os
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def call_anthropic(message: str, language: str = "roman_urdu") -> dict:
    """
    Calls the Anthropic API for a health-guidance response.
    Raises an exception on failure so the worker's retry logic can catch it.
    """
    system_prompt = (
        "You are Sehat Sahara, a bilingual health guidance assistant. "
        "Respond in Roman Urdu and English as appropriate. "
        "If the message contains emergency keywords, prioritize urgent guidance."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": message}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")

    return {
        "reply": text,
        "language": language,
    }
