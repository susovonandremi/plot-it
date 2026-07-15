import pytest
import os
from services.nlp_parser import parse_prompt, is_llm_configured

test_prompts = [
    "1200 sqft plot",
    "100 sqm plot",
    "2 Katha plot"
]

@pytest.mark.skipif(not is_llm_configured() or os.getenv("GROQ_API_KEY") == "mock_key_for_testing", reason="Requires live Groq API key")
def test_units():
    for prompt in test_prompts:
        result = parse_prompt(prompt)
        print(f"Prompt: {prompt}")
        print(f"Detected System: {result['original_unit_system']['system']}")
        print(f"Normalized Size: {result['plot_size_sqft']} sqft")
        print("-" * 20)
        assert result['plot_size_sqft'] > 0

