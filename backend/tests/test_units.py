from services.nlp_parser import parse_prompt

test_prompts = [
    "1200 sqft plot",
    "100 sqm plot",
    "2 Katha plot"
]

for prompt in test_prompts:
    result = parse_prompt(prompt)
    print(f"Prompt: {prompt}")
    print(f"Detected System: {result['original_unit_system']['system']}")
    print(f"Normalized Size: {result['plot_size_sqft']} sqft")
    print("-" * 20)
