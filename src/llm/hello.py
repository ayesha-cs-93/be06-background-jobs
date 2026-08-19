"""
Stage 0 checkpoint script.
Run: python -m dotenv run -- python src/llm/hello.py
(or just `python src/llm/hello.py` if you load .env another way)

Confirms: the provider, base URL, and API key actually work before
any real code depends on them.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)

res = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
)

print(res.choices[0].message.content)
