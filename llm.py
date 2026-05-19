"""
Thin LLM wrapper using LiteLLM for provider-agnostic model calls.

Supports Anthropic, OpenAI, Google, Mistral, Manus, and any provider LiteLLM supports.
Configure via environment variables:
  - LLM_MODEL: model identifier (default: anthropic/claude-haiku-4-5-20251001)
  - LLM_CLASSIFY_MODEL: override model for classification (optional)
  - LLM_ACTIVATE_MODEL: override model for activation (optional)

Model format follows LiteLLM conventions:
  - Anthropic: anthropic/claude-haiku-4-5-20251001
  - OpenAI:    openai/gpt-4o-mini
  - Google:    gemini/gemini-2.0-flash
  - Mistral:   mistral/mistral-small-latest
  - Manus:     manus/manus-1.6, manus/manus-1.6-lite, manus/manus-1.6-max

Set the appropriate API key env var for your provider:
  - ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, MANUS_API_KEY, etc.
"""

import os
import time

import litellm


DEFAULT_MODEL = "anthropic/claude-haiku-4-5-20251001"

# Polling config for async providers (Manus)
POLL_INTERVAL = 5  # seconds between status checks
POLL_TIMEOUT = 300  # max seconds to wait


def get_model(task: str = "default") -> str:
    """Get the model to use for a given task.
    Checks task-specific override first, then falls back to LLM_MODEL, then default."""
    task_var = f"LLM_{task.upper()}_MODEL"
    return os.environ.get(task_var) or os.environ.get("LLM_MODEL") or DEFAULT_MODEL


def _is_async_provider(model: str) -> bool:
    """Check if the model uses an async provider that requires polling."""
    return model.startswith("manus/")


def _chat_sync(model: str, system: str, user: str, max_tokens: int) -> str:
    """Standard synchronous chat completion (Anthropic, OpenAI, Gemini, Mistral, etc.)."""
    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _chat_async_poll(model: str, system: str, user: str, max_tokens: int) -> str:
    """Async provider flow: submit task, poll until complete (Manus)."""
    prompt = f"{system}\n\n{user}"

    response = litellm.responses(
        model=model,
        input=prompt,
        max_output_tokens=max_tokens,
    )

    task_id = response.id
    elapsed = 0

    while response.status in ("running", "pending"):
        if elapsed >= POLL_TIMEOUT:
            raise TimeoutError(f"LLM task {task_id} timed out after {POLL_TIMEOUT}s")
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        response = litellm.get_responses(
            response_id=task_id,
        )

    if response.status == "completed":
        for message in response.output:
            if message.role == "assistant":
                for block in message.content:
                    if hasattr(block, "text"):
                        return block.text
        raise ValueError(f"LLM task {task_id} completed but no text output found")

    raise RuntimeError(f"LLM task {task_id} failed with status: {response.status}")


def chat(
    system: str,
    user: str,
    task: str = "default",
    max_tokens: int = 1000,
) -> str:
    """Send a chat request and return the text response.
    Automatically handles sync providers (Anthropic, OpenAI, etc.)
    and async providers (Manus) that require polling."""
    model = get_model(task)

    if _is_async_provider(model):
        return _chat_async_poll(model, system, user, max_tokens)
    return _chat_sync(model, system, user, max_tokens)
