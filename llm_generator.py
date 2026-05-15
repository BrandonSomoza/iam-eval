import json
import re
import os
from openai import OpenAI
from together import Together

groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY")
)

together_client = Together(
    api_key=os.environ.get("TOGETHER_API_KEY")
)

TOGETHER_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "Qwen/Qwen2.5-7B-Instruct-Turbo",
    "meta-llama/Meta-Llama-3-8B-Instruct-Lite",
]

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]


def extract_json(content: str):
    if not content:
        return None

    match = re.search(r"```json(.*?)```", content, re.DOTALL)
    if match:
        content = match.group(1).strip()

    try:
        return json.loads(content)
    except:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass

    return None


def generate_actions(prompt: str, model: str = "llama-3.3-70b-versatile"):
    system_prompt = """
You are an AWS IAM policy generator.

Return ONLY valid JSON in this format:

{
  "Action": ["service:Action1", "service:Action2"]
}

Rules:
- No explanations
- No markdown
- No code blocks
- Only JSON
"""

    if model in TOGETHER_MODELS:
        response = together_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
    else:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

    content = response.choices[0].message.content
    parsed = extract_json(content)

    if parsed and "Action" in parsed:
        actions = parsed["Action"]

        if not isinstance(actions, list):
            raise ValueError("LLM returned non-list Action field")

        actions = [a.strip() for a in actions if isinstance(a, str)]
        return actions

    raise ValueError(f"Failed to parse LLM output: {content}")