"""Base agent infrastructure: shared LLM calling via OpenRouter."""
import json
import os
import urllib.request
from typing import Optional


def _get_openrouter_key() -> Optional[str]:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        import subprocess
        try:
            result = subprocess.run(
                ["bash", "-c", "source /home/gregjones/.hermes/.env 2>/dev/null && echo \"$OPENROUTER_API_KEY\""],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                api_key = result.stdout.strip()
        except Exception:
            pass
    return api_key


def call_llm(
    system_prompt: str,
    user_prompt: str,
    model: str = "openai/gpt-4o",
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> Optional[str]:
    """
    Call OpenRouter with a system + user prompt.
    Returns the response text, or None on failure.
    """
    api_key = _get_openrouter_key()
    if not api_key:
        return None

    try:
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode()

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://fable-studio.local",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[AgentBase] API call failed: {e}")
        return None