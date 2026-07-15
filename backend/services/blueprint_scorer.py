import logging
"""
Blueprint Scoring Dashboard — Multi-Axis Quality Score
========================================================
Computes a radar-chart worthy score across 5 axes:
1. Vastu Compliance (from vastu_engine)
2. Space Efficiency (room area vs plot area)
3. Accessibility (all rooms reachable via doors)
4. Room Proportions (aspect ratio quality)
5. Ventilation Potential (exterior walls with windows)

Outputs a dict suitable for rendering as an SVG radar chart.
"""

from typing import List, Dict, Any, Optional
import math

from services.constants import WALL_ADJACENCY_TOL

logger = logging.getLogger(__name__)


def _score_space_efficiency(placed_rooms: List[Dict], plot_area: float) -> float:
    """Score how well the layout uses available space (target: 80-90% utilization)."""
    total_room_area = sum(r.get('width', 0) * r.get('height', 0) for r in placed_rooms)
    if plot_area <= 0:
        return 50.0

    ratio = total_room_area / plot_area
    # Perfect is around 85% utilization
    if 0.78 <= ratio <= 0.92:
        return 100.0
    elif 0.70 <= ratio < 0.78:
        return 85.0
    elif 0.92 < ratio <= 1.0:
        return 80.0
    elif ratio > 1.0:
        return max(0, 100 - (ratio - 1.0) * 200)
    else:
        return max(0, ratio / 0.70 * 70)


def _score_accessibility(accessibility_report: Optional[Dict]) -> float:
    """Score based on room accessibility graph completeness."""
    if not accessibility_report:
        return 70.0  # No data = neutral

    if accessibility_report.get('is_fully_accessible', False):
        return 100.0

    total = len(accessibility_report.get('reachable', [])) + len(accessibility_report.get('isolated', []))
    if total == 0:
        return 50.0

    reachable_ratio = len(accessibility_report.get('reachable', [])) / total
    return round(reachable_ratio * 100, 1)


def _score_proportions(proportion_report: Optional[Dict]) -> float:
    """Score from proportion validator."""
    if not proportion_report:
        return 70.0
    return max(0, min(100, proportion_report.get('proportion_score', 70)))


def _score_ventilation(
    placed_rooms: List[Dict],
    plot_width: float,
    plot_height: float,
    windows: Optional[List[Dict]] = None,
) -> float:
    """
    Score cross-ventilation potential.
    Cross-references exterior wall proximity with actual window placements
    to distinguish between "potential" and "realized" ventilation.
    """
    if not placed_rooms:
        return 50.0

    # Build a set of room IDs that have at least one window
    rooms_with_windows = set()
    if windows:
        for win in windows:
            rid = win.get('room_id', '')
            if rid:
                rooms_with_windows.add(rid)

    scores = []

    # Find actual physical envelope bounds to support setback offsets
    physical_rooms = [r for r in placed_rooms if not r.get('is_annotation', False)]
    if not physical_rooms:
        physical_rooms = placed_rooms
    min_x = min(r['x'] for r in physical_rooms) if physical_rooms else 0.0
    min_y = min(r['y'] for r in physical_rooms) if physical_rooms else 0.0
    max_x = max(r['x'] + r['width'] for r in physical_rooms) if physical_rooms else plot_width
    max_y = max(r['y'] + r['height'] for r in physical_rooms) if physical_rooms else plot_height

    for room in placed_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']
        rid = room.get('id', '')
        exterior_walls = 0

        if abs(rx - min_x) <= WALL_ADJACENCY_TOL:
            exterior_walls += 1  # West wall
        if abs(ry - min_y) <= WALL_ADJACENCY_TOL:
            exterior_walls += 1  # North wall
        if abs(rx + rw - max_x) <= WALL_ADJACENCY_TOL:
            exterior_walls += 1  # East wall
        if abs(ry + rh - max_y) <= WALL_ADJACENCY_TOL:
            exterior_walls += 1  # South wall

        has_window = rid in rooms_with_windows

        if exterior_walls >= 2 and has_window:
            scores.append(100)
        elif exterior_walls >= 2:
            scores.append(75)   # Potential but no window placed
        elif exterior_walls == 1 and has_window:
            scores.append(65)
        elif exterior_walls == 1:
            scores.append(50)
        else:
            scores.append(30)   # Interior room

    return round(sum(scores) / len(scores), 1) if scores else 50.0


def score_blueprint(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    vastu_score: Optional[Dict] = None,
    accessibility_report: Optional[Dict] = None,
    proportion_report: Optional[Dict] = None,
    windows: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Compute a multi-axis blueprint quality score.

    Returns:
        {
            "overall": float,  # Weighted average (0-100)
            "axes": {
                "vastu": float,
                "space_efficiency": float,
                "accessibility": float,
                "proportions": float,
                "ventilation": float,
            },
            "grade": str,  # A/B/C/D/F
            "label": str,  # "Excellent" / "Good" / etc.
        }
    """
    plot_area = plot_width * plot_height

    axes = {
        "vastu": vastu_score.get('score', 70) if vastu_score else 70.0,
        "space_efficiency": _score_space_efficiency(placed_rooms, plot_area),
        "accessibility": _score_accessibility(accessibility_report),
        "proportions": _score_proportions(proportion_report),
        "ventilation": _score_ventilation(placed_rooms, plot_width, plot_height, windows),
    }

    # Weighted average
    weights = {
        "vastu": 0.20,
        "space_efficiency": 0.20,
        "accessibility": 0.25,
        "proportions": 0.20,
        "ventilation": 0.15,
    }

    overall = sum(axes[k] * weights[k] for k in axes)
    overall = round(overall, 1)

    # ── MULTIPLICATIVE GATE ────────────────────────────────────────────
    # Critical axes that MUST pass for a livable layout.
    # If accessibility or proportions are critically low, cap overall
    # to a failing grade regardless of other scores.
    gate_failed = False
    if axes["accessibility"] < 50:
        overall = min(overall, 49.0)
        gate_failed = True
        logger.warning(f"Accessibility gate FAILED ({axes['accessibility']}) — capping to F")
    if axes["proportions"] < 40:
        overall = min(overall, 49.0)
        gate_failed = True
        logger.warning(f"Proportions gate FAILED ({axes['proportions']}) — capping to F")

    # Grade
    if overall >= 90:
        grade, label = "A+", "Outstanding"
    elif overall >= 80:
        grade, label = "A", "Excellent"
    elif overall >= 70:
        grade, label = "B", "Good"
    elif overall >= 60:
        grade, label = "C", "Average"
    elif overall >= 50:
        grade, label = "D", "Below Average"
    else:
        grade, label = "F", "Needs Improvement"

    return {
        "overall": overall,
        "axes": axes,
        "grade": grade,
        "label": label,
        "gate_failed": gate_failed,
    }