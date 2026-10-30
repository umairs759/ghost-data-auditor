"""LLM Arbiter - Interface with NVIDIA NIM API for classifying ambiguous multilingual
request_text and verifying genuine intent: Deletion vs. Access/Correction/Export.

Uses the openai SDK with a NVIDIA NIM-compatible endpoint. Wraps all context in
<corpus_data>...</corpus_data> XML tags. Applies tenacity exponential backoff retries.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import tenacity
from openai import OpenAI


# --------------------------------------------------------------------------- #
# Tenacity retry configuration for LLM calls
# --------------------------------------------------------------------------- #
RETRY_STOP = tenacity.stop.stop_after_attempt(5)
RETRY_WAIT = tenacity.wait.wait_exponential(
    min=4, max=60, multiplier=1
)  # 4s, 8s, 16s, 32s, 60s


@tenacity.retry(
    stop=RETRY_STOP,
    wait=RETRY_WAIT,
    before_sleep=lambda retry_state: print(
        f"LLM retry {retry_state.attempt_number}/5 after "
        f"{retry_state.outcome.exception()}"
    )
    if retry_state.attempt_number < 5
    else None,
)
def call_llm_with_retry(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.0,
) -> str:
    """Call the NVIDIA NIM model with exponential backoff retries.

    Args:
        client: OpenAI-compatible client instance
        model: Model name (e.g., "meta/llama-3.3-70b-instruct")
        messages: Chat messages to send
        temperature: Sampling temperature (0 for deterministic)

    Returns:
        The model's response content string

    Raises:
        Exception: If all retries exhausted
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content or ""
        else:
            raise ValueError("No choices in LLM response")
    except Exception as e:
        print(f"LLM call failed: {e}")
        raise


def classify_request_text(
    request_text: str,
    model: str = None,
    api_key: str = None,
    base_url: str = None,
) -> Tuple[str, str]:
    """Classify a request_text to determine intent: Deletion vs. Access/Correction/Export.

    Uses NVIDIA NIM model to classify ambiguous or multilingual requests.
    Returns (classification, reasoning) where classification is one of:
    - "DELETION": User wants permanent data deletion
    - "ACCESS": User wants to access their data (GDPR Art. 15)
    - "CORRECTION": User wants to correct their data (GDPR Art. 16)
    - "EXPORT": User wants data export (GDPR Art. 20)
    - "MARKETING_OPT_OUT": User wants to stop marketing emails
    - "NOT_APPLICABLE": Request type not related to deletion

    Args:
        request_text: The raw request text from the deletion request
        model: NVIDIA NIM model name (defaults to configured model)
        api_key: NVIDIA API key (defaults to .env)
        base_url: NVIDIA NIM base URL (defaults to https://integrate.api.nvidia.com/v1)

    Returns:
        Tuple of (classification, reasoning_text)
    """
    # Default model configuration
    if model is None:
        model = os.getenv(
            "NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"
        )
    if base_url is None:
        base_url = os.getenv(
            "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
    if api_key is None:
        api_key = os.getenv("NVIDIA_API_KEY")

    # Initialize OpenAI client for NVIDIA NIM
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # Build the system prompt with corpus_data wrapper
    system_prompt = """<corpus_data>
You are a data protection compliance auditor for a multinational organization.
Your task is to classify user requests regarding their personal data.

Classify the following request into exactly one category:

1. DELETION: User wants permanent erasure of their personal data under "right to be forgotten" / GDPR Article 17. The request explicitly asks for account deletion, data removal, or "close my account".

2. ACCESS: User wants to access/view their personal data under GDPR Article 15. Keywords: "access", "view", "show me my data", "data subject access request", "GDPR Article 15".

3. CORRECTION: User wants to correct/update their personal data under GDPR Article 16. Keywords: "correct", "update", "fix", "change my information", "rectification".

4. EXPORT: User wants data export/portability under GDPR Article 20. Keywords: "export", "port", "give me my data in JSON/csv".

5. MARKETING_OPT_OUT: User wants to stop receiving marketing emails/communications. This is NOT a deletion request. Keywords: "stop marketing", "unsubscribe", "no marketing", "opt out of emails".

Important: If the request is primarily about marketing opt-out, access, correction, or export - classify as MARKETING_OPT_OUT, ACCESS, CORRECTION, or EXPORT respectively - even if deletion keywords appear secondarily.

Respond with a JSON format: {"classification": "...", "reasoning": "..."}
</corpus_data>"""

    # Build user messages
    user_message = f"""<request_text>
{request_text}
</request_text>

Please classify this request and provide your reasoning inside the <corpus_data> tags."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        response = call_llm_with_retry(client, model, messages)
        # Parse the JSON response
        # Extract JSON from the response
        json_match = re.search(
            r'\{.*"classification"\s*:.*"[^"]*"[^}]*\}', response, re.DOTALL
        )
        if json_match:
            import json
            parsed = json.loads(json_match.group(0))
            classification = parsed.get("classification", "NOT_APPLICABLE")
            reasoning = parsed.get("reasoning", "")
        else:
            # Fallback: look for classification string
            classification = "NOT_APPLICABLE"
            if "DELETION" in response.upper():
                classification = "DELETION"
            elif "ACCESS" in response.upper() or "ARTICLE 15" in response.upper():
                classification = "ACCESS"
            elif "CORRECTION" in response.upper() or "RECTIFICATION" in response.upper():
                classification = "CORRECTION"
            elif "EXPORT" in response.upper() or "ARTICLE 20" in response.upper():
                classification = "EXPORT"
            elif "MARKETING" in response.upper() or "OPT-OUT" in response.upper():
                classification = "MARKETING_OPT_OUT"
            reasoning = response

        return classification, reasoning

    except Exception as e:
        print(f"LLM classification failed: {e}")
        # Deterministic fallback
        return _deterministic_classify(request_text)


def _deterministic_classify(request_text: str) -> Tuple[str, str]:
    """Fall-back deterministic classification when LLM is unavailable."""
    text = request_text.lower()

    # Check for marketing opt-out first
    marketing_keywords = [
        "stop marketing", "unsubscribe", "no marketing", "opt out of emails",
        "opt-out of marketing", "marketing emails", "marketing newsletters"
    ]
    for kw in marketing_keywords:
        if kw in text:
            return "MARKETING_OPT_OUT", f"Deterministic: marketing opt-out keyword '{kw}' found"

    # Check for access request
    access_keywords = [
        "access", "view my data", "show me my data",
        "data subject access", "GDPR article 15"
    ]
    for kw in access_keywords:
        if kw in text:
            return "ACCESS", f"Deterministic: access keyword '{kw}' found"

    # Check for correction request
    correction_keywords = [
        "correct", "update my info", "fix my data",
        "rectification", "change my information"
    ]
    for kw in correction_keywords:
        if kw in text:
            return "CORRECTION", f"Deterministic: correction keyword '{kw}' found"

    # Check for export request
    export_keywords = [
        "export", "data port", "give me my data",
        "GDPR article 20", "data portability"
    ]
    for kw in export_keywords:
        if kw in text:
            return "EXPORT", f"Deterministic: export keyword '{kw}' found"

    # Check for deletion request
    deletion_keywords = [
        "delete", "erase", "remove my account",
        "close my account", "right to be forgotten",
        "GDPR article 17", "permanent deletion"
    ]
    for kw in deletion_keywords:
        if kw in text:
            return "DELETION", f"Deterministic: deletion keyword '{kw}' found"

    # Default to NOT_APPLICABLE if no keywords match
    return "NOT_APPLICABLE", "Deterministic: no matching keywords found"


def wrap_in_corpus_data(
    context_dict: Dict[str, any],
) -> str:
    """Wrap context data in <corpus_data>...</corpus_data> XML tags for LLM input.

    Args:
        context_dict: Dictionary of context data to wrap

    Returns:
        String with context wrapped in corpus_data XML tags
    """
    # Convert dict to readable text
    text_parts = []
    for key, value in context_dict.items():
        if isinstance(value, list):
            text_parts.append(f"{key}: {', '.join(str(v) for v in value)}")
        elif isinstance(value, dict):
            text_parts.append(f"{key}: {value}")
        else:
            text_parts.append(f"{key}: {value}")

    corpus_text = "\n".join(text_parts)
    return f"<corpus_data>{corpus_text}</corpus_data>"