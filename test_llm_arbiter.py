import sys
sys.path.insert(0, r'C:\Users\usamah\Desktop\Hackerrank_hackathon')
from core.llm_arbiter import classify_request_text, _deterministic_classify

# Test deterministic classification
test_cases = [
    ("Please close my account and process the associated personal-data deletion.", "DELETION"),
    ("Please stop sending me marketing emails.", "MARKETING_OPT_OUT"),
    ("I want to access my personal data under GDPR Article 15.", "ACCESS"),
    ("Please correct my address information.", "CORRECTION"),
    ("I want to export my data.", "EXPORT"),
    ("Stop sending me marketing newsletters.", "MARKETING_OPT_OUT"),
    ("Japanese request: テスト", "NOT_APPLICABLE"),  # Will fall through to deterministic
]

print('LLM Arbiter classification tests:')
for request_text, expected in test_cases:
    classification, reasoning = _deterministic_classify(request_text)
    status = "✓" if classification == expected else "✗"
    print(f"  {status} '{request_text[:50]}...' => {classification} (expected: {expected})")
    print(f"    Reasoning: {reasoning[:80]}...")