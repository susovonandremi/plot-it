"""
Solar & Wind Analysis Engine
==============================
Computes sun exposure and cross-ventilation scoring for each room.

Sun Path:
  - Uses latitude + compass orientation to determine which rooms
    get morning sun (East), afternoon sun (West).
  - Assigns sun-hours estimate based on exterior wall exposure.

Ventilation:
  - Identifies rooms with windows on 2+ exterior walls (cross-ventilation).
  - Scores airflow paths between opposing windows.
"""
import logging

from typing import List, Dict, Any, Optional
import math

logger = logging.getLogger(__name__)


# ── SUN EXPOSURE ──────────────────────────────────────────────────────────────

def calculate_sun_exposure(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    latitude: float = 12.0,  # Default: South India (~12°N)
    orientation: str = "N",   # Which direction the plot faces
) -> List[Dict[str, Any]]:
    """
    Estimates daily sun-hours for each room based on exterior wall exposure.

    Returns per-room sun exposure data:
    [
        {
            "room_id": str,
            "sun_hours": float,
            "exposure_sides": ["E", "S"],
            "rating": "high" | "medium" | "low",
        }
    ]
    """
    TOL = 0.5
    results = []

    for room in placed_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']

        sides = []
        if rx <= TOL:
            sides.append("W")
        if abs(rx + rw - plot_width) <= TOL:
            sides.append("E")
        if ry <= TOL:
            sides.append("N")
        if abs(ry + rh - plot_height) <= TOL:
            sides.append("S")

        # Estimate sun hours based on exposed sides
        sun_hours = 0.0
        for side in sides:
            if side == "E":
                sun_hours += 3.5  # Morning sun
            elif side == "W":
                sun_hours += 3.5  # Afternoon sun
            elif side == "S":
                # In Northern Hemisphere, south gets most sun
                sun_hours += 5.0 if latitude > 0 else 2.0
            elif side == "N":
                sun_hours += 2.0 if latitude > 0 else 5.0

        # Rating
        if sun_hours >= 6:
            rating = "high"
        elif sun_hours >= 3:
            rating = "medium"
        else:
            rating = "low"

        results.append({
            "room_id": room["id"],
            "room_type": room["type"],
            "sun_hours": round(sun_hours, 1),
            "exposure_sides": sides,
            "rating": rating,
        })

    return results


# ── CROSS-VENTILATION ─────────────────────────────────────────────────────────

def score_ventilation(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    windows: Optional[List[Dict]] = None,
) -> List[Dict[str, Any]]:
    """
    Scores cross-ventilation potential for each room.

    Cross-ventilation requires openings (windows/doors) on at least 2 opposing walls.
    Corner rooms with 2 exterior walls score highest.

    Returns per-room ventilation data:
    [
        {
            "room_id": str,
            "exterior_walls": int,
            "has_cross_ventilation": bool,
            "ventilation_score": float (0-100),
            "wind_flow_direction": optional str ("NW-SE", "E-W", etc.)
        }
    ]
    """
    TOL = 0.5
    results = []

    for room in placed_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']

        ext_walls = set()
        if rx <= TOL:
            ext_walls.add("W")
        if abs(rx + rw - plot_width) <= TOL:
            ext_walls.add("E")
        if ry <= TOL:
            ext_walls.add("N")
        if abs(ry + rh - plot_height) <= TOL:
            ext_walls.add("S")

        n_ext = len(ext_walls)

        # Cross-ventilation check
        has_cross = False
        flow_dir = None
        if "N" in ext_walls and "S" in ext_walls:
            has_cross = True
            flow_dir = "N-S"
        elif "E" in ext_walls and "W" in ext_walls:
            has_cross = True
            flow_dir = "E-W"
        elif n_ext >= 2:
            has_cross = True
            flow_dir = "-".join(sorted(ext_walls))

        # Score
        if has_cross:
            score = 100.0
        elif n_ext >= 2:
            score = 85.0
        elif n_ext == 1:
            score = 55.0
        else:
            score = 20.0

        results.append({
            "room_id": room["id"],
            "room_type": room["type"],
            "exterior_walls": n_ext,
            "has_cross_ventilation": has_cross,
            "ventilation_score": score,
            "wind_flow_direction": flow_dir,
        })

    return results


# ── SUMMARY ──────────────────────────────────────────────────────────────────

def analyze_environment(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    latitude: float = 12.0,
) -> Dict[str, Any]:
    """
    Combined solar + ventilation analysis.

    Returns:
        {
            "sun_exposure": [...],
            "ventilation": [...],
            "overall_sun_score": float,
            "overall_vent_score": float,
        }
    """
    sun = calculate_sun_exposure(placed_rooms, plot_width, plot_height, latitude)
    vent = score_ventilation(placed_rooms, plot_width, plot_height)

    avg_sun = sum(s["sun_hours"] for s in sun) / max(len(sun), 1)
    avg_vent = sum(v["ventilation_score"] for v in vent) / max(len(vent), 1)

    return {
        "sun_exposure": sun,
        "ventilation": vent,
        "overall_sun_score": round(avg_sun * 10, 1),  # Normalize to 0-100 scale
        "overall_vent_score": round(avg_vent, 1),
    }