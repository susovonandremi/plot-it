"""
Structural Engine — Feature E: Beam & Column Mapping
=====================================================
Computes tentative structural element positions for a given room layout.

This is NOT a full structural engineering calculation — it is a heuristic
approximation based on architectural conventions:
- Columns at plot corners (always)
- Columns at room corners that align on 2+ shared walls
- Columns on a regular grid every ~15ft (standard RCC frame spacing)
- Load-bearing walls: walls shared by 3+ rooms or spanning full plot width/height
- Beams: connecting columns along shared wall lines

Output is rendered as a toggleable SVG layer for visual reference.
"""
import logging
import math
from typing import List, Dict, Any, Tuple, Set, Optional

# ── Shapely computational geometry ────────────────────────────────────────────
from shapely.geometry import Polygon, box as shapely_box, mapping
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

COLUMN_WIDTH_FT = 0.75        # 9 inches
COLUMN_DEPTH_FT = 1.0         # 12 inches
STANDARD_SPAN_FT = 15.0       # Standard RCC column spacing in feet
WALL_THICKNESS_FT = 0.75      # 9-inch exterior walls
LOAD_BEARING_MIN_ROOMS = 2    # Min rooms sharing a wall for it to be load-bearing


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

class ColumnPoint:
    def __init__(self, x: float, y: float, reason: str = "grid"):
        self.x = round(x, 2)
        self.y = round(y, 2)
        self.width = COLUMN_WIDTH_FT
        self.height = COLUMN_DEPTH_FT
        self.reason = reason  # "corner" | "junction" | "grid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x - self.width / 2,
            "y": self.y - self.height / 2,
            "cx": self.x,
            "cy": self.y,
            "width": self.width,
            "height": self.height,
            "reason": self.reason,
        }

    def __eq__(self, other):
        return abs(self.x - other.x) < 1.0 and abs(self.y - other.y) < 1.0

    def __hash__(self):
        return hash((round(self.x), round(self.y)))


class BeamSegment:
    def __init__(self, x1: float, y1: float, x2: float, y2: float, beam_type: str = "primary"):
        self.x1 = round(x1, 2)
        self.y1 = round(y1, 2)
        self.x2 = round(x2, 2)
        self.y2 = round(y2, 2)
        self.beam_type = beam_type  # "primary" | "secondary"
        self.length = round(math.hypot(x2 - x1, y2 - y1), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x1": self.x1, "y1": self.y1,
            "x2": self.x2, "y2": self.y2,
            "length_ft": self.length,
            "beam_type": self.beam_type,
        }


class WallBoundaryGeometry:
    """
    Unified "Wall Boundary" represented as a 2-D Shapely Polygon.

    Instead of modelling each wall as a 1-D line segment, the boundary is
    the *area* of the plot that is NOT occupied by any (inward-buffered)
    room polygon.  This naturally captures:

    - All internal party walls between adjacent rooms
    - The external perimeter wall
    - Any residual structural voids / columns implied by gaps in packing

    Construction
    ------------
    Use :func:`generate_wall_boundary` rather than instantiating directly.
    """

    def __init__(self, boundary_polygon: Polygon, wall_thickness: float):
        self.polygon: Polygon = boundary_polygon
        self.wall_thickness: float = wall_thickness

    # ── Convenience ──────────────────────────────────────────────────────────

    @property
    def area(self) -> float:
        """Total area (ft² or m²) covered by walls."""
        return self.polygon.area

    @property
    def is_valid(self) -> bool:
        """True when the underlying Shapely geometry is topologically valid."""
        return self.polygon.is_valid and not self.polygon.is_empty

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise the wall boundary for API / renderer consumption.

        Returns a GeoJSON-compatible ``geometry`` fragment plus summary metrics.
        The SVG renderer should use the ``geometry`` coordinates to draw the
        wall fill layer; the structural engine's *column* and *beam* layers
        sit on top of it unchanged.
        """
        geom = mapping(self.polygon)  # GeoJSON-style dict
        bounds = self.polygon.bounds  # (minx, miny, maxx, maxy)
        return {
            "type": "wall_boundary",
            "wall_thickness": self.wall_thickness,
            "wall_area": round(self.area, 4),
            "bounds": {
                "minx": round(bounds[0], 4),
                "miny": round(bounds[1], 4),
                "maxx": round(bounds[2], 4),
                "maxy": round(bounds[3], 4),
            },
            "geometry": geom,  # GeoJSON Polygon / MultiPolygon
        }


# ── MODULE-LEVEL GEOMETRY FUNCTION ───────────────────────────────────────────

def generate_wall_boundary(
    room_polygons: List[Polygon],
    plot_polygon: Polygon,
    ext_thickness: float = 0.75,  # 9-inch exterior
    int_thickness: float = 0.375, # 4.5-inch interior
) -> WallBoundaryGeometry:
    """
    Compute a unified wall-boundary polygon with variable thickness support.
    
    Algorithm:
    1. For each room, determine which of its 4 edges are 'EXTERIOR' (touching plot bounds) 
       or 'INTERIOR' (shared with another room or internal).
    2. Create a shrunken room polygon using these custom offsets.
    3. Subtract from plot.
    """
    # Use the actual bounds of the building (rooms) for exterior wall detection
    if room_polygons:
        all_xs = [p.bounds[0] for p in room_polygons] + [p.bounds[2] for p in room_polygons]
        all_ys = [p.bounds[1] for p in room_polygons] + [p.bounds[3] for p in room_polygons]
        effective_min_x = min(all_xs)
        effective_min_y = min(all_ys)
        effective_max_x = max(all_xs)
        effective_max_y = max(all_ys)
    else:
        effective_min_x, effective_min_y, effective_max_x, effective_max_y = plot_polygon.bounds

    TOL = 0.5 # 6-inch tolerance for boundary check
    
    shrunken: List[Polygon] = []
    for poly in room_polygons:
        b = poly.bounds # (x1, y1, x2, y2)
        
        # Determine offsets for 4 sides: left, bottom, right, top
        # Default to interior thickness
        offsets = [int_thickness/2.0] * 4
        
        # Left edge (x = b[0])
        if abs(b[0] - effective_min_x) < TOL: offsets[0] = ext_thickness / 2.0
        # Bottom edge (y = b[1])
        if abs(b[1] - effective_min_y) < TOL: offsets[1] = ext_thickness / 2.0
        # Right edge (x = b[2])
        if abs(b[2] - effective_max_x) < TOL: offsets[2] = ext_thickness / 2.0
        # Top edge (y = b[3])
        if abs(b[3] - effective_max_y) < TOL: offsets[3] = ext_thickness / 2.0
        
        # For interior edges that are NOT shared with another room (unlikely in dense CP-SAT),
        # we still use int_thickness. But wait, if two rooms are 1ft apart, 
        # the space between them is already wall area.
        
        # Create shrunken rectangle
        shrunk_rect = shapely_box(
            b[0] + offsets[0],
            b[1] + offsets[1],
            b[2] - offsets[2],
            b[3] - offsets[3]
        )
        
        if not shrunk_rect.is_empty and shrunk_rect.area > 0:
            shrunken.append(shrunk_rect)

    if not shrunken:
        return WallBoundaryGeometry(plot_polygon, ext_thickness)

    shrunken_union = unary_union(shrunken)
    wall_boundary_poly = plot_polygon.difference(shrunken_union)

    return WallBoundaryGeometry(wall_boundary_poly, ext_thickness)


# ── STRUCTURAL ENGINE ─────────────────────────────────────────────────────────

class StructuralEngine:
    """
    Computes structural elements (columns, beams, load-bearing walls)
    from a placed room layout.
    """

    def __init__(self, plot_width: float, plot_height: float):
        self.plot_width = plot_width
        self.plot_height = plot_height

    def analyze(self, placed_rooms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Full structural analysis pipeline.

        Returns:
            {
                "columns": [ColumnPoint.to_dict(), ...],
                "beams": [BeamSegment.to_dict(), ...],
                "load_bearing_walls": [LoadBearingWall.to_dict(), ...],
                "structural_summary": {...}
            }
        """
        columns = self.find_column_positions(placed_rooms)
        wall_boundary = self.build_wall_boundary(placed_rooms)
        beams = self.calculate_beam_spans(columns)

        return {
            "columns": [c.to_dict() for c in columns],
            "beams": [b.to_dict() for b in beams],
            "wall_boundary": wall_boundary.to_dict(),
            "structural_summary": {
                "total_columns": len(columns),
                "total_beams": len(beams),
                "wall_boundary_area": round(wall_boundary.area, 4),
                "wall_thickness": WALL_THICKNESS_FT,
                "estimated_column_spacing_ft": STANDARD_SPAN_FT,
                "structural_system": self._classify_structural_system(
                    columns, wall_boundary
                ),
            },
        }

    def find_column_positions(self, placed_rooms: List[Dict[str, Any]]) -> List[ColumnPoint]:
        """
        Finds tentative column positions using three strategies:
        1. Plot corners (always)
        2. Room corners that align with 2+ other room corners (structural junctions)
        3. Regular grid at STANDARD_SPAN_FT intervals
        """
        columns: Set[ColumnPoint] = set()

        # Strategy 1: Plot corners
        for cx, cy in [(0, 0), (self.plot_width, 0),
                       (0, self.plot_height), (self.plot_width, self.plot_height)]:
            columns.add(ColumnPoint(cx, cy, reason="corner"))

        # Strategy 2: Room corners that are structural junctions
        # A junction is a point where 2+ room corners meet
        corner_counts: Dict[Tuple[int, int], int] = {}
        for room in placed_rooms:
            rx, ry = room.get("x", 0), room.get("y", 0)
            rw, rh = room.get("width", 0), room.get("height", 0)

            # Snapping to 0.5ft grid (matches solver SCALE=2)
            def snap_grid(val):
                return round(val * 2) / 2

            room_corners = [
                (snap_grid(rx), snap_grid(ry)),
                (snap_grid(rx + rw), snap_grid(ry)),
                (snap_grid(rx), snap_grid(ry + rh)),
                (snap_grid(rx + rw), snap_grid(ry + rh)),
            ]
            for corner in room_corners:
                corner_counts[corner] = corner_counts.get(corner, 0) + 1

        for (cx, cy), count in corner_counts.items():
            if count >= 2:  # Junction of 2+ rooms
                columns.add(ColumnPoint(float(cx), float(cy), reason="junction"))

        # Strategy 3: Regular grid columns (fill gaps)
        def _is_on_room_boundary(cx: float, cy: float, placed_rooms: list, tol: float = 1.0) -> bool:
            """Return True if (cx,cy) is near a room corner or shared wall, False if interior."""
            for room in placed_rooms:
                rx, ry = room.get('x', 0), room.get('y', 0)
                rw, rh = room.get('width', 0), room.get('height', 0)
                # Check if point is strictly inside room (not on boundary)
                if (rx + tol < cx < rx + rw - tol) and (ry + tol < cy < ry + rh - tol):
                    return False  # Deep interior of a single room
            return True

        x = STANDARD_SPAN_FT
        while x < self.plot_width:
            y = STANDARD_SPAN_FT
            while y < self.plot_height:
                candidate = ColumnPoint(x, y, reason="grid")
                # Only add if not already covered by a nearby column
                if not any(abs(c.x - x) < STANDARD_SPAN_FT * 0.4 and
                           abs(c.y - y) < STANDARD_SPAN_FT * 0.4
                           for c in columns):
                    # Ensure grid columns land on walls, not floating in open space
                    if _is_on_room_boundary(x, y, placed_rooms, tol=2.0):
                        columns.add(candidate)
                y += STANDARD_SPAN_FT
            x += STANDARD_SPAN_FT

        # Sort for deterministic output
        sorted_cols = sorted(columns, key=lambda c: (round(c.y / 5) * 5, round(c.x / 5) * 5))
        return sorted_cols

    def build_wall_boundary(
        self, placed_rooms: List[Dict[str, Any]]
    ) -> WallBoundaryGeometry:
        """
        Build the unified **Wall Boundary** polygon using Shapely boolean ops.

        Each room dict is converted to a Shapely ``box`` polygon, then
        delegated to the module-level :func:`generate_wall_boundary` function
        which shrinks rooms inward by ``WALL_THICKNESS_FT / 2`` and subtracts
        the union from the plot polygon.

        Parameters
        ----------
        placed_rooms : list of dict
            Legacy room dicts with ``x``, ``y``, ``width``, ``height`` keys.

        Returns
        -------
        WallBoundaryGeometry
        """
        plot_polygon: Polygon = shapely_box(
            0.0, 0.0, self.plot_width, self.plot_height
        )

        room_polygons: List[Polygon] = []
        for room in placed_rooms:
            rx = float(room.get("x", 0))
            ry = float(room.get("y", 0))
            rw = float(room.get("width", 0))
            rh = float(room.get("height", 0))
            if rw > 0 and rh > 0:
                room_polygons.append(shapely_box(rx, ry, rx + rw, ry + rh))

        return generate_wall_boundary(
            room_polygons=room_polygons,
            plot_polygon=plot_polygon,
            ext_thickness=WALL_THICKNESS_FT,
            int_thickness=WALL_THICKNESS_FT / 2,
        )

    def calculate_beam_spans(self, columns: List[ColumnPoint]) -> List[BeamSegment]:
        """
        Connects columns with beam segments.
        Strategy: Connect columns that are aligned horizontally or vertically
        within STANDARD_SPAN_FT distance.
        """
        beams: List[BeamSegment] = []
        used_pairs: Set[Tuple[int, int]] = set()

        for i, col_a in enumerate(columns):
            for j, col_b in enumerate(columns):
                if i >= j:
                    continue
                pair_key = (min(i, j), max(i, j))
                if pair_key in used_pairs:
                    continue

                dx = abs(col_a.x - col_b.x)
                dy = abs(col_a.y - col_b.y)
                dist = math.hypot(dx, dy)

                # Only connect if aligned (horizontal or vertical) and within span
                is_horizontal = dy < 1.0 and dx <= STANDARD_SPAN_FT * 1.1
                is_vertical = dx < 1.0 and dy <= STANDARD_SPAN_FT * 1.1

                if is_horizontal or is_vertical:
                    beam_type = "primary" if (col_a.reason in ("corner", "junction") and
                                              col_b.reason in ("corner", "junction")) else "secondary"
                    beams.append(BeamSegment(
                        col_a.x, col_a.y, col_b.x, col_b.y,
                        beam_type=beam_type
                    ))
                    used_pairs.add(pair_key)

        return beams

    def _classify_structural_system(
        self,
        columns: List[ColumnPoint],
        wall_boundary: Optional[WallBoundaryGeometry] = None,
    ) -> str:
        """
        Classifies the structural system based on column count and the ratio
        of wall area to total plot area.
        """
        col_count = len(columns)
        plot_area = self.plot_width * self.plot_height

        # Wall-to-plot area ratio — higher ratio implies more masonry
        wall_ratio: float = 0.0
        if wall_boundary is not None and plot_area > 0:
            wall_ratio = wall_boundary.area / plot_area

        if col_count > 20:
            return "RCC Frame Structure (Multi-bay)"
        elif col_count > 8:
            return "RCC Frame Structure (Standard)"
        elif wall_ratio > 0.25:
            # Wall material covers >25% of floor area → masonry-dominant
            return "Load-Bearing Wall Structure"
        else:
            return "Simple Frame Structure"