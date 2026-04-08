"""
Style Engine — Feature C: Architectural Style Presets (RAG-lite)
================================================================
A curated knowledge base of architectural styles with specific:
- Room adjacency preferences
- Proportion guidelines (aspect ratios, min/max sizes)
- Mandatory rooms (always include)
- Forbidden rooms (never include)
- Spatial character (open plan vs. cellular, courtyard vs. linear)

The NLP layer detects style intent from the prompt, and this engine
injects the appropriate constraints into the generation pipeline.

Supported styles:
  - kerala_traditional
  - minimalist_modern
  - mughal_courtyard
  - colonial_bungalow
  - contemporary_villa
  - studio_apartment
  - duplex_townhouse
"""
import logging

import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── STYLE PRESETS ─────────────────────────────────────────────────────────────

STYLE_PRESETS: Dict[str, Dict[str, Any]] = {

    "kerala_traditional": {
        "display_name": "Kerala Traditional (Nalukettu)",
        "description": "Central courtyard (Nadumuttam) with rooms arranged around it. Sloped roofs, verandahs, and a strong Vastu orientation.",
        "character": "courtyard_centric",
        "mandatory_rooms": [
            {"type": "Verandah", "count": 1, "special_notes": "Front verandah (Poomukham)"},
            {"type": "Pooja Room", "count": 1, "special_notes": "NE corner, mandatory"},
            {"type": "Courtyard", "count": 1, "special_notes": "Central open courtyard (Nadumuttam)"},
        ],
        "forbidden_room_types": ["garage", "gym"],
        "adjacency_preferences": {
            "kitchen": ["dining", "courtyard"],
            "master_bedroom": ["bathroom", "courtyard"],
            "living": ["verandah", "courtyard"],
            "pooja": ["courtyard"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 14, "min_depth_ft": 12, "preferred_aspect": 1.2},
            "bedroom": {"min_width_ft": 12, "min_depth_ft": 11, "preferred_aspect": 1.1},
            "verandah": {"min_width_ft": 8, "min_depth_ft": 6, "preferred_aspect": 2.5},
            "courtyard": {"min_width_ft": 10, "min_depth_ft": 10, "preferred_aspect": 1.0},
        },
        "vastu_weight": 1.5,  # Vastu is extra important for this style
        "keywords": ["kerala", "nalukettu", "traditional", "courtyard", "nadumuttam", "poomukham"]
    },

    "minimalist_modern": {
        "display_name": "Minimalist Modern",
        "description": "Open-plan living with clean lines, large windows, and minimal internal walls. Kitchen-dining-living as one continuous space.",
        "character": "open_plan",
        "mandatory_rooms": [],
        "forbidden_room_types": ["pooja", "verandah"],
        "adjacency_preferences": {
            "kitchen": ["dining", "living"],
            "dining": ["living", "kitchen"],
            "master_bedroom": ["bathroom"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 16, "min_depth_ft": 14, "preferred_aspect": 1.4},
            "kitchen": {"min_width_ft": 10, "min_depth_ft": 8, "preferred_aspect": 1.5},
            "bedroom": {"min_width_ft": 12, "min_depth_ft": 11, "preferred_aspect": 1.1},
        },
        "vastu_weight": 0.5,  # Vastu is less important for this style
        "keywords": ["minimalist", "modern", "contemporary", "open plan", "clean", "sleek", "loft"]
    },

    "mughal_courtyard": {
        "display_name": "Mughal Courtyard",
        "description": "Symmetrical layout with a central garden courtyard, formal reception rooms, and private zenana quarters.",
        "character": "courtyard_centric",
        "mandatory_rooms": [
            {"type": "Courtyard", "count": 1, "special_notes": "Central garden courtyard"},
            {"type": "Foyer", "count": 1, "special_notes": "Grand entrance foyer"},
            {"type": "Dining Room", "count": 1, "special_notes": "Formal dining"},
        ],
        "forbidden_room_types": [],
        "adjacency_preferences": {
            "living": ["foyer", "courtyard"],
            "dining": ["kitchen", "courtyard"],
            "master_bedroom": ["bathroom", "courtyard"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 18, "min_depth_ft": 16, "preferred_aspect": 1.3},
            "foyer": {"min_width_ft": 10, "min_depth_ft": 8, "preferred_aspect": 1.5},
            "courtyard": {"min_width_ft": 14, "min_depth_ft": 14, "preferred_aspect": 1.0},
        },
        "vastu_weight": 1.0,
        "keywords": ["mughal", "courtyard", "haveli", "riad", "islamic", "symmetrical", "garden"]
    },

    "colonial_bungalow": {
        "display_name": "Colonial Bungalow",
        "description": "Single-storey with a wrap-around verandah, high ceilings, and a formal living-dining arrangement.",
        "character": "linear",
        "mandatory_rooms": [
            {"type": "Verandah", "count": 1, "special_notes": "Wrap-around verandah"},
            {"type": "Study", "count": 1, "special_notes": "Home office / library"},
        ],
        "forbidden_room_types": [],
        "adjacency_preferences": {
            "living": ["verandah", "dining"],
            "study": ["living"],
            "kitchen": ["dining", "utility"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 16, "min_depth_ft": 14, "preferred_aspect": 1.2},
            "verandah": {"min_width_ft": 8, "min_depth_ft": 6, "preferred_aspect": 3.0},
            "study": {"min_width_ft": 10, "min_depth_ft": 9, "preferred_aspect": 1.1},
        },
        "vastu_weight": 0.8,
        "keywords": ["colonial", "bungalow", "british", "heritage", "verandah", "plantation", "classic"]
    },

    "contemporary_villa": {
        "display_name": "Contemporary Villa",
        "description": "Multi-level luxury villa with double-height living, home theatre, and landscaped outdoor spaces.",
        "character": "multi_level",
        "mandatory_rooms": [
            {"type": "Home Theatre", "count": 1, "special_notes": "Soundproofed media room"},
            {"type": "Gym", "count": 1, "special_notes": "Home fitness room"},
            {"type": "Foyer", "count": 1, "special_notes": "Double-height entrance foyer"},
        ],
        "forbidden_room_types": [],
        "adjacency_preferences": {
            "living": ["foyer", "dining"],
            "gym": ["bathroom"],
            "home_theatre": ["living"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 20, "min_depth_ft": 18, "preferred_aspect": 1.3},
            "master_bedroom": {"min_width_ft": 16, "min_depth_ft": 14, "preferred_aspect": 1.2},
            "foyer": {"min_width_ft": 12, "min_depth_ft": 10, "preferred_aspect": 1.2},
        },
        "vastu_weight": 0.7,
        "keywords": ["villa", "luxury", "contemporary", "theatre", "gym", "pool", "premium", "high-end"]
    },

    "studio_apartment": {
        "display_name": "Studio Apartment",
        "description": "Compact single-room living with integrated kitchen and sleeping area. Maximizes every square foot.",
        "character": "open_plan",
        "mandatory_rooms": [],
        "forbidden_room_types": ["pooja", "study", "dining", "verandah", "courtyard"],
        "adjacency_preferences": {
            "kitchen": ["living"],
        },
        "proportion_hints": {
            "living": {"min_width_ft": 10, "min_depth_ft": 10, "preferred_aspect": 1.0},
            "bathroom": {"min_width_ft": 5, "min_depth_ft": 6, "preferred_aspect": 0.8},
        },
        "vastu_weight": 0.3,
        "keywords": ["studio", "apartment", "flat", "compact", "1bhk", "bachelor", "single room"],
    },

    "duplex_townhouse": {
        "display_name": "Duplex Townhouse",
        "description": "Two-floor layout with public spaces on ground floor and private bedrooms on upper floor. Staircase is central.",
        "character": "multi_level",
        "mandatory_rooms": [
            {"type": "Staircase", "count": 1, "special_notes": "Central staircase connecting floors"},
        ],
        "forbidden_room_types": ["courtyard"],
        "adjacency_preferences": {
            "staircase": ["living", "passage"],
            "living": ["dining", "kitchen"],
            "master_bedroom": ["bathroom"],
        },
        "proportion_hints": {
            "staircase": {"min_width_ft": 4, "min_depth_ft": 8, "preferred_aspect": 0.5},
            "living": {"min_width_ft": 14, "min_depth_ft": 12, "preferred_aspect": 1.2},
        },
        "vastu_weight": 1.0,
        "keywords": ["duplex", "townhouse", "two floor", "2 floor", "two storey", "2 storey", "row house"]
    },

    "technical_cad": {
        "display_name": "Engineering CAD Blueprint",
        "description": "Professional technical drawing style. Monochrome, hatched walls, high contrast, and monospace typography. Ideal for construction documentation.",
        "character": "technical",
        "mandatory_rooms": [],
        "forbidden_room_types": [],
        "adjacency_preferences": {},
        "proportion_hints": {
            "living": {"min_width_ft": 14, "min_depth_ft": 12, "preferred_aspect": 1.2},
        },
        "vastu_weight": 1.0,
        "keywords": ["cad", "autocad", "blueprint", "technical", "engineering", "architectural", "working drawing", "professional"]
    },
}

# Default style when none detected
DEFAULT_STYLE = "contemporary_villa"


# ── STYLE DETECTION ───────────────────────────────────────────────────────────

def detect_style(prompt: str) -> Optional[str]:
    """
    Detects architectural style from a natural language prompt using keyword matching.

    Args:
        prompt: The user's natural language prompt

    Returns:
        Style key (e.g. "kerala_traditional") or None if no style detected
    """
    prompt_lower = prompt.lower()

    # Score each style by keyword matches
    style_scores: Dict[str, int] = {}
    for style_key, preset in STYLE_PRESETS.items():
        score = 0
        for keyword in preset["keywords"]:
            if keyword in prompt_lower:
                score += 1
        if score > 0:
            style_scores[style_key] = score

    if not style_scores:
        return None

    # Return the highest-scoring style
    return max(style_scores, key=lambda k: style_scores[k])


def get_style_preset(style_key: str) -> Dict[str, Any]:
    """Returns the style preset dict for a given style key."""
    return STYLE_PRESETS.get(style_key, STYLE_PRESETS[DEFAULT_STYLE])


# ── CONSTRAINT APPLICATION ────────────────────────────────────────────────────

def apply_style_constraints(
    rooms: List[Dict[str, Any]],
    style_key: str,
    plot_size_sqft: float = 0
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Applies style constraints to the room list.

    Actions:
    1. Inject mandatory rooms (if not already present)
    2. Remove forbidden room types
    3. Return proportion hints for the layout engine

    Args:
        rooms: List of room dicts from NLP parser
        style_key: Style identifier
        plot_size_sqft: Plot area for scaling decisions

    Returns:
        (updated_rooms, style_metadata)
        style_metadata includes proportion_hints, vastu_weight, character
    """
    preset = get_style_preset(style_key)

    updated_rooms = list(rooms)

    # 1. Remove forbidden rooms
    forbidden = {f.lower() for f in preset.get("forbidden_room_types", [])}
    if forbidden:
        updated_rooms = [
            r for r in updated_rooms
            if r["type"].lower().replace(" ", "_") not in forbidden
        ]

    # 2. Inject mandatory rooms (if not already present)
    existing_types = {r["type"].lower().replace(" ", "_") for r in updated_rooms}
    for mandatory in preset.get("mandatory_rooms", []):
        mtype_key = mandatory["type"].lower().replace(" ", "_")
        if mtype_key not in existing_types:
            updated_rooms.append({
                "type": mandatory["type"],
                "count": mandatory.get("count", 1),
                "special_notes": mandatory.get("special_notes", ""),
                "style_injected": True,
            })
            existing_types.add(mtype_key)

    # 3. Build metadata
    style_metadata = {
        "style_key": style_key,
        "display_name": preset["display_name"],
        "description": preset["description"],
        "character": preset["character"],
        "proportion_hints": preset.get("proportion_hints", {}),
        "adjacency_preferences": preset.get("adjacency_preferences", {}),
        "vastu_weight": preset.get("vastu_weight", 1.0),
        "color_palette": preset.get("color_palette", {}),
    }

    return updated_rooms, style_metadata


def get_all_style_names() -> List[Dict[str, str]]:
    """Returns a list of all available styles for API documentation."""
    return [
        {"key": k, "name": v["display_name"], "description": v["description"]}
        for k, v in STYLE_PRESETS.items()
    ]