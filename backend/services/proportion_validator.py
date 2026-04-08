"""
Proportion Validator — Room Aspect Ratio Quality Check
=======================================================
Validates that room dimensions are architecturally sound.

Flags rooms with extreme aspect ratios:
  - width/height > 2.5 (too wide/shallow — feels like a corridor)
  - width/height < 0.4 (too narrow/deep — feels like a tunnel)

Also checks minimum dimensions:
  - Bedroom: min 9ft on shortest side
  - Bathroom: min 5ft on shortest side
  - Kitchen: min 7ft on shortest side
  - Living: min 10ft on shortest side
"""
import logging

from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

MAX_ASPECT_RATIO = 2.5  # Maximum width/height ratio
MIN_ASPECT_RATIO = 0.4  # Minimum width/height ratio

# Minimum short-side dimensions (in feet)
MIN_DIMENSIONS = {
    "bedroom": 9.0,
    "master_bedroom": 10.0,
    "bathroom": 5.0,
    "toilet": 4.0,
    "kitchen": 7.0,
    "dining": 8.0,
    "living": 10.0,
    "pooja": 5.0,
    "study": 7.0,
    "store": 4.0,
    "utility": 4.0,
    "passage": 3.5,
    "corridor": 3.5,
    "foyer": 6.0,
    "verandah": 5.0,
    "staircase": 4.0,
}

DEFAULT_MIN_DIM = 4.0


# ── PROPORTION CHECK ──────────────────────────────────────────────────────────

def validate_proportions(
    placed_rooms: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Validates room proportions and returns a report.

    Returns:
        {
            "valid": [room_id, ...],
            "flagged": [{
                "room_id": str,
                "room_type": str,
                "width": float,
                "height": float,
                "aspect_ratio": float,
                "issue": str,
                "severity": "warning" | "error",
                "suggestion": str,
            }, ...],
            "proportion_score": float (0-100),
            "total_rooms": int,
        }
    """
    valid = []
    flagged = []

    for room in placed_rooms:
        room_id = room["id"]
        room_type = room["type"].lower().replace(" ", "_")
        w = room.get("width", 0)
        h = room.get("height", 0)

        if w <= 0 or h <= 0:
            flagged.append({
                "room_id": room_id,
                "room_type": room_type,
                "width": w,
                "height": h,
                "aspect_ratio": 0,
                "issue": "zero_dimension",
                "severity": "error",
                "suggestion": f"Room has invalid dimensions ({w}×{h})"
            })
            continue

        aspect = round(w / h, 2)
        short_side = min(w, h)
        long_side = max(w, h)
        min_dim = MIN_DIMENSIONS.get(room_type, DEFAULT_MIN_DIM)
        issues = []

        # Check aspect ratio
        if aspect > MAX_ASPECT_RATIO:
            issues.append({
                "issue": "too_wide",
                "severity": "warning",
                "suggestion": f"Too wide (ratio {aspect}). Ideal: ≤{MAX_ASPECT_RATIO}. Consider swapping to {round(h, 1)}×{round(w, 1)}"
            })
        elif aspect < MIN_ASPECT_RATIO:
            issues.append({
                "issue": "too_narrow",
                "severity": "warning",
                "suggestion": f"Too narrow (ratio {aspect}). Ideal: ≥{MIN_ASPECT_RATIO}. Consider swapping to {round(h, 1)}×{round(w, 1)}"
            })

        # Check minimum dimension
        if short_side < min_dim:
            issues.append({
                "issue": "too_small",
                "severity": "error",
                "suggestion": f"Short side ({short_side:.1f}ft) below minimum ({min_dim}ft) for {room_type}"
            })

        if issues:
            for issue in issues:
                flagged.append({
                    "room_id": room_id,
                    "room_type": room_type,
                    "width": round(w, 1),
                    "height": round(h, 1),
                    "aspect_ratio": aspect,
                    **issue
                })
        else:
            valid.append(room_id)

    # Calculate proportion score
    total = len(placed_rooms)
    errors = len([f for f in flagged if f["severity"] == "error"])
    warnings = len([f for f in flagged if f["severity"] == "warning"])

    if total > 0:
        score = max(0, round(100 - (errors * 20) - (warnings * 5), 1))
    else:
        score = 100.0

    return {
        "valid": valid,
        "flagged": flagged,
        "proportion_score": score,
        "total_rooms": total,
        "errors": errors,
        "warnings": warnings,
    }