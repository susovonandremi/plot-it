import logging
import os
import json
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ═══════════════════════════════════════════════════════════════
# UNIT NORMALIZATION LAYER
# ═══════════════════════════════════════════════════════════════

# Conversion constants
SQFT_TO_SQM = 0.092903        # 1 sqft = 0.092903 sqm
FEET_TO_METERS = 0.3048       # 1 ft = 0.3048 m
KATHA_TO_SQFT = 720           # 1 Katha (West Bengal) = 720 sqft
KATHA_TO_SQFT_BIHAR = 1361    # 1 Katha (Bihar/Jharkhand) = 1361 sqft

def detect_unit_system(user_prompt: str) -> dict:
    """
    Detects which measurement system the user is using.
    
    Args:
        user_prompt (str): Raw user input
        
    Returns:
        dict: {
            "system": "imperial" | "metric" | "regional",
            "area_unit": "sqft" | "sqm" | "katha",
            "length_unit": "ft" | "m",
            "regional_variant": "west_bengal" | "bihar" | None
        }
    """
    prompt_lower = user_prompt.lower()
    
    # Check for regional units first (most specific)
    if "katha" in prompt_lower or "kattha" in prompt_lower:
        # Determine variant (default: West Bengal)
        variant = "bihar" if any(x in prompt_lower for x in ["bihar", "jharkhand"]) else "west_bengal"
        return {
            "system": "regional",
            "area_unit": "katha",
            "length_unit": "ft",  # Katha users typically use feet for dimensions
            "regional_variant": variant
        }
    
    # Check for metric (sqm takes precedence over meters)
    if any(x in prompt_lower for x in ["sqm", "sq m", "square meter", "square metre"]):
        return {
            "system": "metric",
            "area_unit": "sqm",
            "length_unit": "m",
            "regional_variant": None
        }
    
    # Check for imperial (sqft takes precedence)
    if any(x in prompt_lower for x in ["sqft", "sq ft", "square feet", "square foot"]):
        return {
            "system": "imperial",
            "area_unit": "sqft",
            "length_unit": "ft",
            "regional_variant": None
        }
    
    # Fallback: Check for dimension units
    if any(x in prompt_lower for x in ["meter", "metre", "meters", "metres"]):
        return {
            "system": "metric",
            "area_unit": "sqm",
            "length_unit": "m",
            "regional_variant": None
        }
    
    # Default: Imperial (most common in India)
    return {
        "system": "imperial",
        "area_unit": "sqft",
        "length_unit": "ft",
        "regional_variant": None
    }


def normalize_to_imperial(value: float, unit: str, regional_variant: str = None) -> float:
    """
    Converts any measurement to Imperial (feet/sqft) for internal processing.
    
    Args:
        value (float): The measurement value
        unit (str): "sqft" | "sqm" | "katha" | "ft" | "m"
        regional_variant (str): "west_bengal" | "bihar" | None
        
    Returns:
        float: Value converted to Imperial
    """
    if unit in ["sqft", "ft"]:
        return value  # Already Imperial
    
    elif unit == "sqm":
        return value / SQFT_TO_SQM  # sqm → sqft
    
    elif unit == "m":
        return value / FEET_TO_METERS  # meters → feet
    
    elif unit == "katha":
        if regional_variant == "bihar":
            return value * KATHA_TO_SQFT_BIHAR
        else:  # Default: West Bengal
            return value * KATHA_TO_SQFT
    
    else:
        raise ValueError(f"Unknown unit: {unit}")


def denormalize_from_imperial(value: float, target_unit: str, regional_variant: str = None) -> float:
    """
    Converts Imperial back to user's preferred unit for display.
    
    Args:
        value (float): Value in Imperial (feet/sqft)
        target_unit (str): User's preferred unit
        regional_variant (str): Regional variant if applicable
        
    Returns:
        float: Value converted to target unit
    """
    if target_unit in ["sqft", "ft"]:
        return value  # Already Imperial
    
    elif target_unit == "sqm":
        return value * SQFT_TO_SQM  # sqft → sqm
    
    elif target_unit == "m":
        return value * FEET_TO_METERS  # feet → meters
    
    elif target_unit == "katha":
        if regional_variant == "bihar":
            return value / KATHA_TO_SQFT_BIHAR
        else:
            return value / KATHA_TO_SQFT
    
    else:
        raise ValueError(f"Unknown target unit: {target_unit}")


# ═══════════════════════════════════════════════════════════════
# END UNIT NORMALIZATION LAYER
# ═══════════════════════════════════════════════════════════════

def parse_prompt(user_prompt: str) -> dict:
    """
    Takes a natural language prompt from the user and returns
    structured JSON with plot size, rooms, and orientation.
    NOW DETECTS incomplete input and triggers consultation mode.
    """

    system_prompt = """
    You are an architectural assistant. Extract features from the prompt.
    COMPLETENESS RULES:
    - Set is_complete: true ONLY if you have BOTH:
      1. Clear plot size (e.g. 1200 sqft, 20x40 ft) 
      2. Clear room requirements (e.g. 2 BHK, 3 bedrooms, etc.)
    - If either is missing or vague (e.g. "I want to build a house", "simple home"), set is_complete: false.
    - If size is 0 or missing, set plot_size_sqft to null (do NOT hallucinate 1500).
    - Capture floors count (default 1).

    Always respond with ONLY valid JSON. No explanation text.
    No markdown. No code blocks. Just raw JSON.

    Extract this structure:
    {
      "plot_size_sqft": number or null,
      "plot_width_ft": number or null,
      "plot_height_ft": number or null,
      "plot_shape": "rectangle" | "l-shape" | "irregular" | "unknown",
      "orientation": "north" | "south" | "east" | "west" | "unknown",
      "floors": 1,
      "rooms": [
        {
          "type": "bedroom" | "bathroom" | "kitchen" | "dining" |
                  "living" | "pooja" | "garage" | "study" | "other",
          "count": number,
          "special_notes": string or null
        }
      ],
      "special_requirements": [],
      "missing_info": [],
      "is_complete": true | false
    }

    CRITICAL: Set is_complete to FALSE if:
    - rooms array is empty AND user didn't mention "home" or "house"
    - ONLY plot size given, no room details AND no building type ("home", "office")
    
    Set is_complete to TRUE if:
    - At least one room type is specified with count
    - OR user mentions "home"/"house" (INFER standard rooms: Kitchen, Bedroom, Bathroom, Living, Dining based on plot size)
    
    List what is missing in missing_info array.
    Support English, Hindi, Urdu, Arabic, and Hinglish inputs.
    """

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }

    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers)
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        
        # Clean any accidental markdown formatting
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        parsed = json.loads(raw_text)
    except Exception as e:
        logger.info(f"Error parsing prompt: {e}")
        # Fallback empty structure
        parsed = {
            "plot_size_sqft": None, "rooms": [], "is_complete": False,
            "missing_info": ["parsing_error"]
        }

    # ⭐ UNIT NORMALIZATION
    unit_info = detect_unit_system(user_prompt)
    parsed["original_unit_system"] = unit_info

    if parsed.get("plot_size_sqft"):
        parsed["plot_size_sqft"] = normalize_to_imperial(
            parsed["plot_size_sqft"], 
            unit_info["area_unit"],
            unit_info["regional_variant"]
        )
    
    if parsed.get("plot_width_ft"):
        parsed["plot_width_ft"] = normalize_to_imperial(
            parsed["plot_width_ft"],
            unit_info["length_unit"]
        )
    
    if parsed.get("plot_height_ft"):
        parsed["plot_height_ft"] = normalize_to_imperial(
            parsed["plot_height_ft"],
            unit_info["length_unit"]
        )

    # 4. FINAL COMPLETENESS VALIDATION (Safety Check)
    # Force consultation if critical info is missing regardless of what LLM said
    rooms = parsed.get('rooms', [])
    plot_size = parsed.get('plot_size_sqft', 0)
    
    if not plot_size or plot_size <= 0 or len(rooms) < 2:
        logger.info(f"[NLP] Forcing consultation: plot_size={plot_size}, rooms={len(rooms)}")
        parsed["is_complete"] = False

    # 5. DEFAULT ROOM INJECTION (Only for sparse but valid complete prompts)
    current_rooms = parsed.get('rooms', [])
    has_kitchen = any('KITCHEN' in r['type'].upper() for r in current_rooms)
    
    if parsed.get('is_complete') and plot_size and (len(current_rooms) < 3 or not has_kitchen):
        logger.info(f"[NLP] Sparse room list for complete prompt. Plot Size: {plot_size}. Injecting defaults.")
        
        defaults = []
        if plot_size >= 2500:
            defaults = [
                {"type": "Master Bedroom", "count": 2},
                {"type": "Bedroom", "count": 2},
                {"type": "Kitchen", "count": 1},
                {"type": "Dining Room", "count": 1},
                {"type": "Living Room", "count": 1},
                {"type": "Bathroom", "count": 3},
                {"type": "Staff Room", "count": 1},
                {"type": "Pooja Room", "count": 1}
            ]
        elif plot_size >= 1500:
            defaults = [
                {"type": "Master Bedroom", "count": 1},
                {"type": "Bedroom", "count": 2},
                {"type": "Kitchen", "count": 1},
                {"type": "Dining Room", "count": 1},
                {"type": "Living Room", "count": 1},
                {"type": "Bathroom", "count": 2},
                {"type": "Pooja Room", "count": 1} 
            ]
        elif plot_size >= 800:
            # ... (rest of defaults)
            defaults = [
                {"type": "Master Bedroom", "count": 1},
                {"type": "Bedroom", "count": 1},
                {"type": "Kitchen", "count": 1},
                {"type": "Living Room", "count": 1},
                {"type": "Bathroom", "count": 1}
            ]
        else:
             defaults = [
                {"type": "Bedroom", "count": 1},
                {"type": "Kitchen", "count": 1},
                {"type": "Bathroom", "count": 1}
             ]
        
        current_types = [r['type'].upper().replace(" ", "") for r in current_rooms]
        for default in defaults:
             def_type_clean = default['type'].upper().replace(" ", "")
             if def_type_clean not in current_types:
                 parsed['rooms'].append(default)
        
        logger.info(f"[NLP] Injected defaults. Total rooms now: {len(parsed['rooms'])}")


    # If incomplete, add consultation object
    if not parsed.get("is_complete", False):
        parsed["consultation"] = {
            "needed": True,
            "questions": generate_consultation_questions(parsed)
        }
    else:
        parsed["consultation"] = {"needed": False}
    
    return parsed


def generate_consultation_questions(parsed_data: dict) -> list:
    """
    Generates 4-6 strategic questions based on what info is missing.
    """
    plot_size = parsed_data.get("plot_size_sqft", 0) or 0
    orientation = parsed_data.get("orientation", "unknown")
    missing = parsed_data.get("missing_info", [])
    
    context = f"""
    User has provided:
    - Plot size: {plot_size if plot_size > 0 else 'MISSING'} sqft
    - Orientation: {orientation}
    - Missing: {', '.join(missing)}
    
    Generate exactly 4-6 questions to understand their needs.
    CRITICAL: If Plot size is MISSING, your first question MUST be "What is your total plot area in sqft?"
    
    ALWAYS include these two core questions:
    1. Purpose (home/rental/commercial)
    2. Occupancy (1-2 / 3-4 / 5-6 / 7+ people)
    
    Return ONLY this exact JSON structure:
    [
      {{
        "id": "q1_purpose",
        "text": "What will this building be used for?",
        "type": "single_select",
        "options": [
          {{"id": "home", "label": "Personal residence"}},
          {{"id": "rental", "label": "Rental property"}},
          {{"id": "commercial", "label": "Commercial space"}}
        ],
        "required": true
      }},
      ...
    ]
    """
    
    system_prompt = "You are a consultation assistant for PlotAI. Return ONLY valid JSON."
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context}
        ],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers)
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        raw_text = raw_text.strip()
        # Remove markdown code block wrapping if present
        if raw_text.startswith("```"):
            # Remove opening ``` or ```json
            first_newline = raw_text.find("\n")
            if first_newline != -1:
                raw_text = raw_text[first_newline + 1:]
            # Remove closing ```
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()
        return json.loads(raw_text)
    except Exception as e:
        logger.info(f"Error generating questions: {e}")
        # Robust hardcoded fallback for the UI
        return [
            {
                "id": "q1_purpose",
                "text": "What will this building be used for?",
                "type": "single_select",
                "options": [
                    {"id": "home", "label": "Personal residence"},
                    {"id": "rental", "label": "Rental property"},
                    {"id": "commercial", "label": "Commercial space"}
                ],
                "required": True
            },
            {
                "id": "q2_occupancy",
                "text": "How many people will live/work here?",
                "type": "single_select",
                "options": [
                    {"id": "1-2", "label": "1-2 people"},
                    {"id": "3-4", "label": "3-4 people"},
                    {"id": "5-6", "label": "5-6 people"},
                    {"id": "7+",  "label": "7+ people"}
                ],
                "required": True
            },
            {
                "id": "q3_plot_size",
                "text": "What is your total plot area in sqft?",
                "type": "number",
                "required": True
            }
        ]


def analyze_consultation_answers(plot_data: dict, answers: dict) -> dict:
    """
    Takes user's consultation answers and returns recommended room list.
    """
    plot_size = plot_data.get("plot_size_sqft") or 0
    if isinstance(plot_size, str):
        try:
            plot_size = float(''.join(c for c in plot_size if c.isdigit() or c == '.'))
        except ValueError:
            plot_size = 0
    plot_size = float(plot_size) if plot_size else 0
    orientation = plot_data.get("orientation", "unknown") or "unknown"
    
    context = f"""
    User has a {plot_size if plot_size > 0 else 1200} sqft {orientation}-facing plot.
    Answers: {json.dumps(answers)}
    
    Recommend a room list that fits within {plot_size if plot_size > 0 else 1200} sqft (18% circulation).
    Return ONLY this JSON structure:
    {{
      "recommended_rooms": [
        {{ "type": "bedroom", "count": 3, "reasoning": "..." }},
        ...
      ],
      "plot_size_sqft": {plot_size} or number,
      "total_rooms": 9,
      "estimated_usage": "82% of available space",
      "vastu_preview": "Excellent (95%)"
    }}
    """
    
    system_prompt = "You are an architectural consultant. Return ONLY valid JSON."
    
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context}
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(GROQ_URL, json=payload, headers=headers)
        response.raise_for_status()
        raw_text = response.json()["choices"][0]["message"]["content"]
        raw_text = raw_text.strip()
        # Remove markdown code block wrapping if present
        if raw_text.startswith("```"):
            first_newline = raw_text.find("\n")
            if first_newline != -1:
                raw_text = raw_text[first_newline + 1:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3].strip()
        result = json.loads(raw_text)
        # Validate the response has expected structure
        if not result.get("recommended_rooms"):
            logger.warning(f"Recommendation response missing recommended_rooms: {result}")
            raise ValueError("Malformed recommendation response")
        return result
    except Exception as e:
        logger.info(f"Error analyzing answers: {e}")
        # Return a proper fallback so frontend can render
        return {
            "recommended_rooms": [
                {"type": "Bedroom", "count": 2, "reasoning": "Standard bedrooms for residential use"},
                {"type": "Kitchen", "count": 1, "reasoning": "Central kitchen area"},
                {"type": "Bathroom", "count": 2, "reasoning": "Attached and common bathrooms"},
                {"type": "Living Room", "count": 1, "reasoning": "Open living space"},
                {"type": "Dining Room", "count": 1, "reasoning": "Dedicated dining area"},
            ],
            "plot_size_sqft": plot_size if plot_size and plot_size > 0 else 1200,
            "total_rooms": 7,
            "estimated_usage": "78% of available space",
            "vastu_preview": "Good (80%)"
        }