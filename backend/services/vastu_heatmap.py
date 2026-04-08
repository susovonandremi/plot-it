"""
Vastu Heatmap Engine — Feature B: Vastu 2.0
============================================
Generates a per-room Vastu energy score and produces a spatial heatmap
using bilinear interpolation across the plot grid.

The heatmap can be rendered as a low-opacity color overlay on the SVG blueprint,
giving users an intuitive visual of energy flow (Prana) through the building.

Score interpretation:
  90-100: Excellent (deep green)
  70-89:  Good (light green)
  50-69:  Neutral (yellow)
  30-49:  Weak (orange)
  0-29:   Poor (red)
"""
import logging

import math
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

# Per-room Vastu scores based on type + zone alignment
# Format: {room_type: {zone: score}}
ROOM_ZONE_SCORES: Dict[str, Dict[str, int]] = {
    "MASTER_BEDROOM": {"SW": 100, "S": 70, "W": 60, "NW": 40, "SE": 20, "NE": 10},
    "BEDROOM":        {"W": 90, "NW": 85, "S": 70, "E": 60, "N": 50, "C": 40},
    "KITCHEN":        {"SE": 100, "NW": 70, "E": 60, "S": 40, "N": 20, "NE": 0},
    "LIVING":         {"N": 100, "NE": 90, "E": 80, "C": 60, "W": 40},
    "DINING":         {"W": 90, "E": 80, "N": 60, "C": 50},
    "BATHROOM":       {"S": 90, "W": 80, "NW": 70, "E": 40, "NE": 0},
    "POOJA":          {"NE": 100, "N": 70, "E": 60, "SW": 0, "S": 0},
    "STUDY":          {"W": 90, "SW": 80, "N": 60, "E": 50},
    "STAIRCASE":      {"S": 90, "W": 80, "SW": 85, "N": 30, "NE": 10},
    "PASSAGE":        {"C": 100, "N": 70, "E": 70},
    "ENTRANCE":       {"N": 100, "NE": 90, "E": 80, "S": 30, "SW": 10},
    "GARAGE":         {"SE": 90, "NW": 80, "SW": 40},
}

DEFAULT_SCORE = 50  # Neutral score for unknown room/zone combos

# Heatmap color stops (score → RGB)
COLOR_STOPS: List[Tuple[float, Tuple[int, int, int]]] = [
    (0.0,   (180, 30,  30)),   # Deep red (poor)
    (0.3,   (220, 100, 30)),   # Orange
    (0.5,   (220, 200, 50)),   # Yellow
    (0.7,   (100, 190, 80)),   # Light green
    (1.0,   (20,  140, 60)),   # Deep green (excellent)
]


# ── SCORE CALCULATION ─────────────────────────────────────────────────────────

def calculate_room_vastu_scores(
    placed_rooms: List[Dict[str, Any]],
    vastu_assignments: Dict[str, str]
) -> Dict[str, float]:
    """
    Calculates a 0-100 Vastu energy score for each placed room.

    Args:
        placed_rooms: List of room dicts with 'id', 'type', 'x', 'y', 'width', 'height'
        vastu_assignments: Dict mapping room_id → zone code (e.g. "kitchen_1" → "SE")

    Returns:
        Dict mapping room_id → score (0-100)
    """
    scores: Dict[str, float] = {}

    for room in placed_rooms:
        room_id = room["id"]
        room_type = room["type"].upper().replace(" ", "_")
        zone = vastu_assignments.get(room_id, "C")

        # Look up score table
        type_scores = ROOM_ZONE_SCORES.get(room_type, {})
        score = type_scores.get(zone, DEFAULT_SCORE)

        # Normalize to 0-100
        scores[room_id] = float(max(0, min(100, score)))

    return scores


def apply_vastu_resizing(
    placed_rooms: List[Dict[str, Any]],
    room_scores: Dict[str, float],
    total_area: float,
    max_bonus_pct: float = 0.15
) -> List[Dict[str, Any]]:
    """
    Redistributes a small area bonus to high-scoring rooms.
    High-Vastu rooms get up to `max_bonus_pct` more area.
    Low-Vastu rooms give up area proportionally.

    This is applied as a conceptual hint — the actual geometry is unchanged
    (BSP already placed rooms), but the 'vastu_area_bonus' field is added
    to the room dict for the renderer to annotate.

    Args:
        placed_rooms: List of placed room dicts
        room_scores: Dict of room_id → vastu score (0-100)
        total_area: Total plot area in sqft
        max_bonus_pct: Maximum area bonus as fraction of room area

    Returns:
        Updated room list with 'vastu_score' and 'vastu_area_bonus' fields
    """
    avg_score = sum(room_scores.values()) / max(1, len(room_scores))

    result = []
    for room in placed_rooms:
        room_id = room["id"]
        score = room_scores.get(room_id, DEFAULT_SCORE)
        delta = (score - avg_score) / 100.0  # -0.5 to +0.5
        bonus_pct = delta * max_bonus_pct     # -7.5% to +7.5%

        updated = dict(room)
        updated["vastu_score"] = score
        updated["vastu_area_bonus_pct"] = round(bonus_pct * 100, 1)
        result.append(updated)

    return result


# ── HEATMAP GENERATION ────────────────────────────────────────────────────────

def _interpolate_color(score_normalized: float) -> Tuple[int, int, int]:
    """
    Maps a normalized score (0.0-1.0) to an RGB color using the COLOR_STOPS table.
    Uses linear interpolation between adjacent stops.
    """
    score_normalized = max(0.0, min(1.0, score_normalized))

    for i in range(len(COLOR_STOPS) - 1):
        s0, c0 = COLOR_STOPS[i]
        s1, c1 = COLOR_STOPS[i + 1]
        if s0 <= score_normalized <= s1:
            t = (score_normalized - s0) / (s1 - s0)
            r = int(c0[0] + t * (c1[0] - c0[0]))
            g = int(c0[1] + t * (c1[1] - c0[1]))
            b = int(c0[2] + t * (c1[2] - c0[2]))
            return (r, g, b)

    return COLOR_STOPS[-1][1]


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def generate_vastu_heatmap(
    placed_rooms: List[Dict[str, Any]],
    room_scores: Dict[str, float],
    resolution_ft: float = 4.0,
    plot_width: float = None,
    plot_height: float = None
) -> Dict[str, Any]:
    """
    Generates a spatial Vastu heatmap using bilinear interpolation.

    Each cell in the grid gets a score based on the weighted influence
    of nearby rooms (inverse-distance weighting).

    Args:
        placed_rooms: List of placed room dicts
        room_scores: Dict of room_id → vastu score (0-100)
        resolution_ft: Grid cell size in feet
        plot_width: Total plot width (auto-detected if None)
        plot_height: Total plot height (auto-detected if None)

    Returns:
        {
            "cells": [{x, y, width, height, score, color, opacity}],
            "resolution_ft": float,
            "min_score": float,
            "max_score": float,
            "avg_score": float,
        }
    """
    if not placed_rooms:
        return {"cells": [], "resolution_ft": resolution_ft, "min_score": 0, "max_score": 0, "avg_score": 0}

    # Auto-detect plot bounds
    if plot_width is None:
        plot_width = max(r["x"] + r["width"] for r in placed_rooms)
    if plot_height is None:
        plot_height = max(r["y"] + r["height"] for r in placed_rooms)

    cols = max(1, int(math.ceil(plot_width / resolution_ft)))
    rows = max(1, int(math.ceil(plot_height / resolution_ft)))

    # Build room centroids with scores
    room_centroids: List[Tuple[float, float, float]] = []
    for room in placed_rooms:
        cx = room["x"] + room["width"] / 2
        cy = room["y"] + room["height"] / 2
        score = room_scores.get(room["id"], DEFAULT_SCORE)
        room_centroids.append((cx, cy, score))

    # Generate grid cells with inverse-distance weighted score
    cells = []
    all_scores = []

    for row in range(rows):
        for col in range(cols):
            cell_cx = col * resolution_ft + resolution_ft / 2
            cell_cy = row * resolution_ft + resolution_ft / 2

            # Inverse-distance weighting (IDW)
            total_weight = 0.0
            weighted_score = 0.0

            for rcx, rcy, rscore in room_centroids:
                dist = math.hypot(cell_cx - rcx, cell_cy - rcy)
                if dist < 0.1:
                    dist = 0.1  # Avoid division by zero
                weight = 1.0 / (dist ** 2)
                weighted_score += weight * rscore
                total_weight += weight

            cell_score = weighted_score / total_weight if total_weight > 0 else DEFAULT_SCORE
            all_scores.append(cell_score)

            # Map score to color
            color_rgb = _interpolate_color(cell_score / 100.0)
            color_hex = _rgb_to_hex(color_rgb)

            # Opacity: higher score = slightly more visible
            opacity = 0.08 + (cell_score / 100.0) * 0.12  # 0.08 to 0.20

            cells.append({
                "x": round(col * resolution_ft, 2),
                "y": round(row * resolution_ft, 2),
                "width": resolution_ft,
                "height": resolution_ft,
                "score": round(cell_score, 1),
                "color": color_hex,
                "opacity": round(opacity, 3),
            })

    return {
        "cells": cells,
        "resolution_ft": resolution_ft,
        "min_score": round(min(all_scores), 1) if all_scores else 0,
        "max_score": round(max(all_scores), 1) if all_scores else 0,
        "avg_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
    }