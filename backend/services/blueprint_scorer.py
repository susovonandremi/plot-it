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


def _score_ventilation(placed_rooms: List[Dict], plot_width: float, plot_height: float) -> float:
    """
    Score cross-ventilation potential.
    Rooms touching 2+ exterior walls get full credit.
    Rooms touching 1 exterior wall get partial credit.
    Interior rooms (0 exterior walls) get low credit.
    """
    if not placed_rooms:
        return 50.0

    TOL = 0.5
    scores = []

    for room in placed_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']
        exterior_walls = 0

        if rx <= TOL:
            exterior_walls += 1  # West wall
        if ry <= TOL:
            exterior_walls += 1  # North wall
        if abs(rx + rw - plot_width) <= TOL:
            exterior_walls += 1  # East wall
        if abs(ry + rh - plot_height) <= TOL:
            exterior_walls += 1  # South wall

        if exterior_walls >= 2:
            scores.append(100)
        elif exterior_walls == 1:
            scores.append(70)
        else:
            scores.append(30)

    return round(sum(scores) / len(scores), 1) if scores else 50.0


def score_blueprint(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    vastu_score: Optional[Dict] = None,
    accessibility_report: Optional[Dict] = None,
    proportion_report: Optional[Dict] = None,
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
        "ventilation": _score_ventilation(placed_rooms, plot_width, plot_height),
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
    }