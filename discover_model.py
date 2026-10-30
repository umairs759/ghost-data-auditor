"""
Temporary script to dynamically discover an active NVIDIA NIM model.

1. Lists available models from the NVIDIA NIM API.
2. Filters for instruct/chat models (llama, mistral, nemotron, qwen).
3. Tries each candidate model with a 1-turn chat completion until one works.
4. Updates NVIDIA_MODEL in .env with the first working active model ID.
5. Logs the selected active model to log.txt.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.logging import logger, log_system, log_error

ENV_FILE = ".env"

MODEL_KEYWORDS = ("llama", "mistral", "nemotron", "qwen")


def discover_available_models(client: OpenAI) -> List[str]:
    """List available models from the NVIDIA NIM API."""
    try:
        models_response = client.models.list()
        model_ids: List[str] = []
        for m in models_response.data:
            mid = getattr(m, "id", None) or str(m)
            model_ids.append(mid)
        log_system(f"Discovered {len(model_ids)} models from NVIDIA NIM API")
        return model_ids
    except Exception as exc:  # noqa: BLE001
        log_error(f"Failed to list models: {exc}")
        return []


def rank_and_filter_models(model_ids: List[str]) -> List[str]:
    """Filter for instruct/chat models and rank by preference."""
    candidates: List[str] = []
    for mid in model_ids:
        lower = mid.lower()
        if any(kw in lower for kw in MODEL_KEYWORDS):
            candidates.append(mid)

    if not candidates:
        log_error("No instruct/chat models found among available models")
        return []

    def rank(mid: str) -> tuple:
        lower = mid.lower()
        nemotron = 0 if "nemotron" in lower else 1
        llama_31 = 0 if "llama-3.1" in lower else 1
        return (nemotron, llama_31, len(mid))

    candidates.sort(key=rank)
    return candidates


def update_env_model(model_id: str) -> None:
    """Update NVIDIA_MODEL in .env file."""
    if not os.path.exists(ENV_FILE):
        log_error(f"{ENV_FILE} not found; cannot update model")
        return

    with open(ENV_FILE, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    updated = False
    new_lines: List[str] = []
    for line in lines:
        if line.startswith("NVIDIA_MODEL="):
            new_lines.append(f"NVIDIA_MODEL={model_id}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"NVIDIA_MODEL={model_id}\n")

    with open(ENV_FILE, "w", encoding="utf-8") as fh:
        fh.writelines(new_lines)

    log_system(f"Updated .env NVIDIA_MODEL={model_id}")


def verify_chat_completion(client: OpenAI, model_id: str) -> bool:
    """Run a 1-turn chat completion to verify the model works."""
    try:
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0,
            max_tokens=10,
        )
        response = completion.choices[0].message.content or ""
        log_system(f"Chat completion verified for model {model_id}: {response[:80]}")
        return True
    except Exception as exc:  # noqa: BLE001
        log_error(f"Chat completion failed for {model_id}: {exc}")
        return False


def main() -> int:
    load_dotenv()
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        log_error("NVIDIA_API_KEY not set in .env")
        return 1

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    # Step 1: Discover models
    model_ids = discover_available_models(client)
    if not model_ids:
        log_error("No models discovered; cannot proceed")
        return 1

    # Step 2: Rank and filter candidates
    candidates = rank_and_filter_models(model_ids)
    if not candidates:
        log_error("No suitable models to try")
        return 1

    log_system(f"Trying {len(candidates)} candidate models in order...")

    # Step 3: Try each candidate until chat completion works
    working_model: Optional[str] = None
    for mid in candidates:
        log_system(f"Attempting model: {mid}")
        if verify_chat_completion(client, mid):
            working_model = mid
            break

    if not working_model:
        log_error("No working model found among candidates")
        return 1

    # Step 4: Update .env
    update_env_model(working_model)

    log_system(f"Model discovery complete. Active model: {working_model}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
