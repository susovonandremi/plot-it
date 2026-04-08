"""
Geometric Validator — Post-Solve Verification
==============================================
Validates that the output of the constraint solver is geometrically
correct before it reaches the SVG renderer.

Checks:
  1. Zero overlaps (pairwise Shapely intersection)
  2. All rooms within plot boundary
  3. Aspect ratio compliance
  4. Coverage percentage
  5. Room dimension sanity (no zero-width rooms)
"""
import logging
from typing import List, Dict, Any, Tuple
from shapely.geometry import box as shapely_box

logger = logging.getLogger(__name__)


def validate_layout(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    max_aspect_ratio: float = 3.0,
) -> Dict[str, Any]:
    """
    Validate a placed room layout for geometric correctness.

    Args:
        placed_rooms: List of room dicts with x, y, width, height
        plot_width, plot_height: Plot dimensions (feet)
        max_aspect_ratio: Maximum allowed width/height ratio

    Returns:
        {
            'is_valid': bool,
            'overlap_count': int,
            'overlap_pairs': [(id1, id2), ...],
            'out_of_bounds': [id, ...],
            'bad_aspect_ratios': [{id, ratio}, ...],
            'coverage_pct': float,
            'total_area': float,
            'warnings': [str, ...],
            'errors': [str, ...],
        }
    """
    errors = []
    warnings = []
    overlap_pairs = []
    out_of_bounds = []
    bad_ratios = []

    if not placed_rooms:
        return {
            'is_valid': False,
            'overlap_count': 0,
            'overlap_pairs': [],
            'out_of_bounds': [],
            'bad_aspect_ratios': [],
            'coverage_pct': 0,
            'total_area': 0,
            'warnings': [],
            'errors': ['No rooms in layout'],
        }

    # Build Shapely boxes
    room_polys = []
    for room in placed_rooms:
        x = float(room.get('x', 0))
        y = float(room.get('y', 0))
        w = float(room.get('width', 0))
        h = float(room.get('height', 0))
        rid = room.get('id', 'unknown')

        if w <= 0 or h <= 0:
            errors.append(f"Room {rid} has zero/negative dimensions ({w}x{h})")
            room_polys.append(None)
            continue

        poly = shapely_box(x, y, x + w, y + h)
        room_polys.append(poly)

        # Check out-of-bounds
        if x < -0.1 or y < -0.1:
            out_of_bounds.append(rid)
            errors.append(f"Room {rid} has negative coordinates ({x}, {y})")
        if x + w > plot_width + 0.5 or y + h > plot_height + 0.5:
            out_of_bounds.append(rid)
            warnings.append(
                f"Room {rid} extends beyond plot "
                f"({x+w:.1f}x{y+h:.1f} > {plot_width}x{plot_height})"
            )

        # Check aspect ratio
        ratio = max(w, h) / min(w, h) if min(w, h) > 0 else float('inf')
        if ratio > max_aspect_ratio:
            bad_ratios.append({'id': rid, 'ratio': round(ratio, 2)})
            warnings.append(
                f"Room {rid} aspect ratio {ratio:.1f} exceeds max {max_aspect_ratio}"
            )

    # Check pairwise overlaps
    n = len(placed_rooms)
    TOLERANCE = 0.15  # Allow tiny overlaps from floating-point rounding
    for i in range(n):
        if room_polys[i] is None:
            continue
        for j in range(i + 1, n):
            if room_polys[j] is None:
                continue

            intersection = room_polys[i].intersection(room_polys[j])
            if intersection.area > TOLERANCE:
                id_a = placed_rooms[i].get('id', f'room_{i}')
                id_b = placed_rooms[j].get('id', f'room_{j}')
                overlap_pairs.append((id_a, id_b))
                errors.append(
                    f"OVERLAP: {id_a} ∩ {id_b} = {intersection.area:.2f} sqft"
                )

    # Coverage
    total_area = sum(
        float(r.get('width', 0)) * float(r.get('height', 0))
        for r in placed_rooms
    )
    plot_area = plot_width * plot_height
    coverage = (total_area / plot_area * 100) if plot_area > 0 else 0

    if coverage < 60:
        warnings.append(f"Low coverage: {coverage:.1f}% (target: >75%)")
    elif coverage > 100:
        errors.append(f"Coverage {coverage:.1f}% exceeds 100% — overlaps present!")

    is_valid = len(errors) == 0

    return {
        'is_valid': is_valid,
        'overlap_count': len(overlap_pairs),
        'overlap_pairs': overlap_pairs,
        'out_of_bounds': out_of_bounds,
        'bad_aspect_ratios': bad_ratios,
        'coverage_pct': round(coverage, 1),
        'total_area': round(total_area, 1),
        'warnings': warnings,
        'errors': errors,
    }
