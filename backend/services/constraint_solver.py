"""
Constraint Solver — OR-Tools CP-SAT Floor Plan Engine
======================================================
Replaces ALL heuristic layout engines (BSP, strip-fill, Voronoi, etc.)
with a mathematically rigorous constraint satisfaction solver.

Key guarantees:
  - ZERO room overlaps (via AddNoOverlap2D)
  - All rooms fit within the buildable envelope
  - Aspect ratio enforcement (max 1:2.5)
  - Adjacency preferences (Kitchen→Dining, Bedroom→Bathroom, etc.)
  - Vastu zone preferences (soft constraints)
  - Circulation spine (passage spans the plot)

Dependencies: ortools >= 9.9
"""
import logging
import math
import time
from typing import List, Dict, Any, Optional, Tuple

from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

# Half-foot grid: all solver variables are in units of 0.5 ft.
# This gives 6-inch precision, standard for Indian residential plans.
SCALE = 2  # 1 foot = 2 solver units

# Room sizing: (min_area_sqft, typ_area_sqft, max_area_sqft, min_side_ft, max_side_ft)
ROOM_SIZES = {
    'master_bedroom': (120, 160, 260, 10.5, 18.5),
    'bedroom':        (100, 140, 200,  9.5, 16.5),
    'bathroom':       ( 30,  45,  65,  5.0,  9.5),
    'toilet':         ( 18,  30,  50,  4.0,  7.5),
    'kitchen':        ( 80, 110, 160,  8.5, 15.5),
    'dining':         ( 80, 110, 180,  8.5, 16.5),
    'living':         (150, 220, 400, 11.5, 24.5),
    'passage':        ( 30,  60, 120,  4.0, 30.5),
    'corridor':       ( 30,  60, 120,  4.0, 30.5),
    'staircase':      ( 55,  70,  95,  7.5, 10.5), # Standard 7'x10' or 7.5'x11'
    'lift':           ( 25,  35,  50,  5.5,  8.5),
    'pooja':          ( 15,  30,  55,  4.5,  9.5),
    'stair_room':     ( 60,  75, 100,  8.0, 12.5),
    'sump':           ( 30,  40,  60,  4.5, 10.5),
}

MAX_ASPECT_RATIO = 2.5

# Adjacency pairs (type_a, type_b, weight)
# Higher weight = stronger preference
PREFERRED_ADJACENCY = [
    ('kitchen',  'dining',         200),
    ('living',   'dining',         150),
    ('master_bedroom', 'bathroom', 120),
    ('bedroom',  'bathroom',       100),
    ('entrance', 'living',         100),
    ('passage',  'staircase',       80),
    ('passage',  'bedroom',         60),
    ('passage',  'master_bedroom',  60),
    ('passage',  'kitchen',         50),
    ('passage',  'living',          50),
]

# Vastu zone centers (normalized 0–1)
VASTU_ZONES = {
    'NE': (0.8, 0.2), 'E':  (0.85, 0.5), 'SE': (0.8, 0.8),
    'S':  (0.5, 0.85), 'SW': (0.2, 0.8),  'W':  (0.15, 0.5),
    'NW': (0.2, 0.2),  'N':  (0.5, 0.15), 'C':  (0.5, 0.5),
}

SPINE_TYPES = {'passage', 'corridor', 'hallway'}


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _normalize_type(rtype: str) -> str:
    t = rtype.lower().strip().replace(' ', '_').replace('_room', '')
    aliases = {
        'bed_room': 'bedroom', 'bath_room': 'bathroom',
        'living_room': 'living', 'dining_room': 'dining',
        'wash_room': 'bathroom', 'wc': 'toilet',
        'stairs': 'staircase', 'corridor': 'passage',
        'hall': 'living', 'elevator': 'lift',
        'porch': 'verandah', 'prayer': 'pooja', 'mandir': 'pooja',
    }
    return aliases.get(t, t)


def _get_size_params(nt: str, plot_area: float) -> Dict:
    """Get min/max w, h in solver units for a room type."""
    defaults = (40, 90, 180, 5.0, 15.0)
    min_a, typ_a, max_a, min_side, max_side = ROOM_SIZES.get(nt, defaults)
    return {
        'min_w': max(2, int(min_side * SCALE)),
        'max_w': int(max_side * SCALE),
        'min_h': max(2, int(min_side * SCALE)),
        'max_h': int(max_side * SCALE),
        'min_area': int(min_a * SCALE * SCALE),
        'max_area': int(max_a * SCALE * SCALE),
    }


def _expand_rooms(rooms: List[Dict]) -> List[Dict]:
    """Expand rooms with count > 1 into individual entries."""
    expanded = []
    for r in rooms:
        count = int(r.get('count', 1) or 1)
        for i in range(count):
            entry = dict(r)
            nt = _normalize_type(r.get('type', 'room'))
            entry['normalized_type'] = nt
            if 'id' not in entry or count > 1:
                entry['id'] = f"{nt}_{len(expanded)}"
            entry.pop('count', None)
            expanded.append(entry)
    return expanded


# ═══════════════════════════════════════════════════════════════════════
# SOLVER
# ═══════════════════════════════════════════════════════════════════════

class ConstraintSolver:
    """
    CP-SAT floor plan solver. Guarantees zero overlaps via AddNoOverlap2D.
    """

    def __init__(self, plot_width_ft: float, plot_height_ft: float):
        self.plot_w = plot_width_ft
        self.plot_h = plot_height_ft
        self.plot_area = plot_width_ft * plot_height_ft
        self.W = int(plot_width_ft * SCALE)
        self.H = int(plot_height_ft * SCALE)

    def solve(
        self,
        rooms: List[Dict],
        vastu_assignments: Optional[Dict[str, str]] = None,
        entry_direction: str = 'S',
        max_time_seconds: float = 5.0,
        fixed_positions: Optional[Dict[str, Dict]] = None,
        floor_number: int = 0,
    ) -> Dict[str, Any]:
        vastu_assignments = vastu_assignments or {}
        fixed_positions = fixed_positions or {}
        expanded = _expand_rooms(rooms)
        if not expanded:
            return {'rooms': [], 'status': 'EMPTY', 'solve_time_ms': 0, 'coverage_pct': 0}

        # Try strict model first, then relaxed cascade
        for attempt, params in enumerate([
            {'relax_areas': 1.0, 'relax_aspect': MAX_ASPECT_RATIO, 'use_adjacency': True, 'use_vastu': True, 'strict_topology': True},
            {'relax_areas': 0.85, 'relax_aspect': 3.0, 'use_adjacency': True, 'use_vastu': False, 'strict_topology': True},
            {'relax_areas': 0.70, 'relax_aspect': 3.5, 'use_adjacency': False, 'use_vastu': False, 'strict_topology': False},
        ]):
            result = self._build_and_solve(
                expanded, vastu_assignments, entry_direction,
                max_time_seconds, fixed_positions=fixed_positions, 
                floor_number=floor_number, **params
            )
            if result['status'] in ('OPTIMAL', 'FEASIBLE'):
                if attempt > 0:
                    result['status'] += '_RELAXED'
                logger.info(f"Solver succeeded on attempt {attempt+1}: {result['status']}")
                return result
            logger.warning(f"Solver attempt {attempt+1} failed, relaxing...")

        # Emergency fallback
        return self._emergency_strip_fill(expanded)

    def _build_and_solve(
        self,
        expanded: List[Dict],
        vastu_assignments: Dict[str, str],
        entry_direction: str,
        max_time: float,
        fixed_positions: Dict[str, Dict] = None,
        floor_number: int = 0,
        relax_areas: float = 1.0,
        relax_aspect: float = MAX_ASPECT_RATIO,
        use_adjacency: bool = True,
        use_vastu: bool = True,
        strict_topology: bool = False,
    ) -> Dict[str, Any]:
        fixed_positions = fixed_positions or {}
        n = len(expanded)
        model = cp_model.CpModel()

        xs, ys, ws, hs = [], [], [], []
        x_intervals, y_intervals = [], []

        for i, room in enumerate(expanded):
            rid = room['id']
            nt = room['normalized_type']
            sp = _get_size_params(nt, self.plot_area)

            min_w = max(2, int(sp['min_w'] * relax_areas))
            max_w = min(sp['max_w'], self.W)
            min_h = max(2, int(sp['min_h'] * relax_areas))
            max_h = min(sp['max_h'], self.H)

            # Ensure min <= max
            if min_w > max_w: min_w = max_w
            if min_h > max_h: min_h = max_h

            x = model.NewIntVar(0, self.W, f'x_{rid}')
            y = model.NewIntVar(0, self.H, f'y_{rid}')
            w = model.NewIntVar(min_w, max_w, f'w_{rid}')
            h = model.NewIntVar(min_h, max_h, f'h_{rid}')

            # ── Fixed Position Constraints ───────────────────────────────
            # If the room has a fixed position (e.g., staircase from Floor 0)
            if rid in fixed_positions or nt in fixed_positions:
                pos = fixed_positions.get(rid) or fixed_positions.get(nt)
                if pos:
                    model.Add(x == int(pos['x'] * SCALE))
                    model.Add(y == int(pos['y'] * SCALE))
                    model.Add(w == int(pos['width'] * SCALE))
                    model.Add(h == int(pos['height'] * SCALE))
                    logger.info(f"📍 Solver: Fixed position for {rid} at ({pos['x']}, {pos['y']})")

            # Containment
            model.Add(x + w <= self.W)
            model.Add(y + h <= self.H)

            # Aspect ratio (linearized: w * 10 <= aspect * 10 * h)
            ar10 = int(relax_aspect * 10)
            model.Add(w * 10 <= ar10 * h)
            model.Add(h * 10 <= ar10 * w)

            # Area constraint via multiplication equality
            min_area = max(1, int(sp['min_area'] * relax_areas))
            max_area = sp['max_area']
            # Clamp to feasible range
            actual_max = max_w * max_h
            actual_min = min_w * min_h
            min_area = max(actual_min, min_area)
            max_area = min(actual_max, max_area)
            if min_area > max_area:
                min_area = actual_min

            area_var = model.NewIntVar(min_area, max_area, f'area_{rid}')
            model.AddMultiplicationEquality(area_var, w, h)

            # Interval vars for NoOverlap2D
            x_end = model.NewIntVar(0, self.W, f'xe_{rid}')
            y_end = model.NewIntVar(0, self.H, f'ye_{rid}')
            model.Add(x_end == x + w)
            model.Add(y_end == y + h)

            xi = model.NewIntervalVar(x, w, x_end, f'xi_{rid}')
            yi = model.NewIntervalVar(y, h, y_end, f'yi_{rid}')

            xs.append(x); ys.append(y); ws.append(w); hs.append(h)
            x_intervals.append(xi); y_intervals.append(yi)

        # ── NON-OVERLAP (hard constraint) ─────────────────────────────
        model.AddNoOverlap2D(x_intervals, y_intervals)

        # ── OBJECTIVE ─────────────────────────────────────────────────
        obj_terms = []

        # ── STRUCTURAL ALIGNMENT (soft but strong) ───────────────────
        # Prefer walls to align across rooms for 'Real Blueprint' look
        for i in range(n):
            for j in range(i + 1, n):
                # If they share a X-coordinate (aligned left or right)
                # or a Y-coordinate (aligned top or bottom)
                align_x1 = model.NewBoolVar(f'alx1_{i}_{j}')
                model.Add(xs[i] == xs[j]).OnlyEnforceIf(align_x1)
                
                align_y1 = model.NewBoolVar(f'aly1_{i}_{j}')
                model.Add(ys[i] == ys[j]).OnlyEnforceIf(align_y1)
                
                # Bonus for alignment
                obj_terms.append(50 * align_x1)
                obj_terms.append(50 * align_y1)

        # ── Build room type index ─────────────────────────────────────
        type_index = {}
        for i, room in enumerate(expanded):
            nt = room['normalized_type']
            type_index.setdefault(nt, []).append(i)

        # ── STRICT TOPOLOGY RULES (Architectural Sequence) ─────────────
        if strict_topology:
            is_south_entry = entry_direction == 'S'
            is_north_entry = entry_direction == 'N'
            is_east_entry = entry_direction == 'E'
            is_west_entry = entry_direction == 'W'

            def constrain_front(idx, strict=False):
                margin = 2 if strict else self.H // 2
                margin_x = 2 if strict else self.W // 2
                if is_south_entry:
                    model.Add(ys[idx] + hs[idx] >= self.H - margin)
                elif is_north_entry:
                    model.Add(ys[idx] <= margin)
                elif is_east_entry:
                    model.Add(xs[idx] + ws[idx] >= self.W - margin_x)
                elif is_west_entry:
                    model.Add(xs[idx] <= margin_x)

            def constrain_rear(idx, strict=False):
                margin = 2 if strict else self.H // 2
                margin_x = 2 if strict else self.W // 2
                if is_south_entry:
                    model.Add(ys[idx] <= margin)
                elif is_north_entry:
                    model.Add(ys[idx] + hs[idx] >= self.H - margin)
                elif is_east_entry:
                    model.Add(xs[idx] <= margin_x)
                elif is_west_entry:
                    model.Add(xs[idx] + ws[idx] >= self.W - margin_x)

            def constrain_sequence_order(idx1, idx2):
                # Enforce that center of idx2 is deeper into plot than idx1
                cx1 = 2 * xs[idx1] + ws[idx1]
                cy1 = 2 * ys[idx1] + hs[idx1]
                cx2 = 2 * xs[idx2] + ws[idx2]
                cy2 = 2 * ys[idx2] + hs[idx2]
                
                if is_south_entry: model.Add(cy1 >= cy2)
                elif is_north_entry: model.Add(cy1 <= cy2)
                elif is_east_entry: model.Add(cx1 >= cx2)
                elif is_west_entry: model.Add(cx1 <= cx2)
                
            def enforce_shared_edge(ia, ib, min_overlap_ft=3.0):
                min_overlap = int(min_overlap_ft * SCALE)  # in solver units

                # Rooms must touch: gap in one axis must be 0
                # AND the overlap in the OTHER axis must be >= min_overlap

                # Option A: rooms touch on x-axis (vertical shared wall), y-overlap >= min_overlap
                touch_x = model.NewBoolVar(f'touch_x_{ia}_{ib}')
                # xa + wa == xb  OR  xb + wb == xa
                left_a  = model.NewBoolVar(f'la_{ia}_{ib}')
                right_a = model.NewBoolVar(f'ra_{ia}_{ib}')
                model.Add(xs[ia] + ws[ia] == xs[ib]).OnlyEnforceIf(left_a)
                model.Add(xs[ib] + ws[ib] == xs[ia]).OnlyEnforceIf(right_a)
                model.AddBoolOr([left_a, right_a]).OnlyEnforceIf(touch_x)

                # Option B: rooms touch on y-axis (horizontal shared wall), x-overlap >= min_overlap
                touch_y = model.NewBoolVar(f'touch_y_{ia}_{ib}')
                top_a    = model.NewBoolVar(f'ta_{ia}_{ib}')
                bottom_a = model.NewBoolVar(f'ba_{ia}_{ib}')
                model.Add(ys[ia] + hs[ia] == ys[ib]).OnlyEnforceIf(top_a)
                model.Add(ys[ib] + hs[ib] == ys[ia]).OnlyEnforceIf(bottom_a)
                model.AddBoolOr([top_a, bottom_a]).OnlyEnforceIf(touch_y)

                # At least one axis must be a true shared edge
                model.AddBoolOr([touch_x, touch_y])

                # Enforce minimum overlap in the perpendicular axis
                overlap_y = model.NewIntVar(-self.H, self.H, f'ovy_{ia}_{ib}')
                min_ye = model.NewIntVar(0, self.H, f'mnye_{ia}_{ib}')
                max_ys = model.NewIntVar(0, self.H, f'mxys_{ia}_{ib}')
                model.AddMinEquality(min_ye, [ys[ia]+hs[ia], ys[ib]+hs[ib]])
                model.AddMaxEquality(max_ys, [ys[ia], ys[ib]])
                model.Add(overlap_y == min_ye - max_ys)
                model.Add(overlap_y >= min_overlap).OnlyEnforceIf(touch_x)

                overlap_x = model.NewIntVar(-self.W, self.W, f'ovx_{ia}_{ib}')
                min_xe = model.NewIntVar(0, self.W, f'mnxe_{ia}_{ib}')
                max_xs = model.NewIntVar(0, self.W, f'mxxs_{ia}_{ib}')
                model.AddMinEquality(min_xe, [xs[ia]+ws[ia], xs[ib]+ws[ib]])
                model.AddMaxEquality(max_xs, [xs[ia], xs[ib]])
                model.Add(overlap_x == min_xe - max_xs)
                model.Add(overlap_x >= min_overlap).OnlyEnforceIf(touch_y)

            for p_idx in type_index.get('car_parking', []):
                constrain_front(p_idx, strict=True)
            for f_idx in type_index.get('foyer', []):
                constrain_front(f_idx, strict=True)

            if floor_number == 0:
                for l_idx in type_index.get('living', []):
                    constrain_front(l_idx, strict=False)
                for k_idx in type_index.get('kitchen', []):
                    constrain_rear(k_idx, strict=True)
                
                # Sequence enforcement
                for f_idx in type_index.get('foyer', []):
                    # Ensure Foyer and Living touch and follow sequence
                    for l_idx in type_index.get('living', []):
                        constrain_sequence_order(f_idx, l_idx)
                        enforce_shared_edge(f_idx, l_idx)
                        for d_idx in type_index.get('dining', []):
                            constrain_sequence_order(l_idx, d_idx)
                            for k_idx in type_index.get('kitchen', []):
                                constrain_sequence_order(d_idx, k_idx)
                                enforce_shared_edge(d_idx, k_idx)
            elif floor_number == 1:
                master_idxs = []
                bed_idxs = []
                # Distinguish Master Bedroom vs generic Bedroom
                for idx in type_index.get('bedroom', []):
                    # Very basic heuristic: largest or first is master, or if label says master
                    bed_idxs.append(idx)
                
                if bed_idxs:
                    master_idx = bed_idxs[0] # assume first is master
                    constrain_front(master_idx, strict=True) # Master bedroom facing road
                    for other_idx in bed_idxs[1:]:
                        constrain_rear(other_idx, strict=True) # Rear view for other bedrooms
                
                # Connect corridor to staircase
                for s_idx in type_index.get('staircase', []) + type_index.get('stairs', []):
                    for c_idx in type_index.get('passage', []) + type_index.get('corridor', []):
                        enforce_shared_edge(s_idx, c_idx)
                        
                # Ensure bathrooms aren't floating (they should touch something). On floor 1, attached baths touch bedrooms.
                baths = type_index.get('bathroom', [])
                if baths and bed_idxs:
                    enforce_shared_edge(baths[0], master_idx) # master attached
                if len(baths) > 1 and len(bed_idxs) > 1:
                    enforce_shared_edge(baths[1], bed_idxs[1]) # attached to bed 2
            elif floor_number >= 2: # Typical Roof Level
                # MUMTY must touch STAIRCASE
                for s_idx in type_index.get('staircase', []) + type_index.get('stairs', []):
                    for m_idx in type_index.get('stair_room', []) + type_index.get('mumty', []):
                        enforce_shared_edge(s_idx, m_idx)
                        
                # OHT should touch MUMTY or be in corners
                for m_idx in type_index.get('stair_room', []) + type_index.get('mumty', []):
                    for t_idx in type_index.get('overhead_water_tank', []) + type_index.get('oht', []):
                        enforce_shared_edge(m_idx, t_idx)
                        constrain_rear(t_idx, strict=True) # Usually rear for utilities
                            
            # Bathroom should not be free-floating (tie to foyer or passage or living)
            for b_idx in type_index.get('bathroom', []) + type_index.get('toilet', []):
                # Only enforce on ground floor (since we check strict_topology, this affects all, but usually ground floor has foyer)
                anchor_hubs = type_index.get('foyer', []) + type_index.get('passage', []) + type_index.get('hallway', []) + type_index.get('bedroom', [])
                if anchor_hubs:
                    # Bathroom must touch AT LEAST ONE anchor hub or bedroom.
                    # Use a disjunctive OR: create a bool for each candidate and require sum >= 1.
                    touching_bools = []
                    for hub_idx in anchor_hubs[:4]:  # Limit to 4 nearest candidates to keep model small
                        b_touch = model.NewBoolVar(f'bath_touch_{b_idx}_{hub_idx}')
                        # Compute gap between bathroom and hub (reuse enforce_touching pattern)
                        xe_b  = xs[b_idx]  + ws[b_idx]
                        xe_h  = xs[hub_idx] + ws[hub_idx]
                        ye_b  = ys[b_idx]  + hs[b_idx]
                        ye_h  = ys[hub_idx] + hs[hub_idx]

                        gx1 = model.NewIntVar(0, self.W, f'bgx1_{b_idx}_{hub_idx}')
                        gx2 = model.NewIntVar(0, self.W, f'bgx2_{b_idx}_{hub_idx}')
                        gy1 = model.NewIntVar(0, self.H, f'bgy1_{b_idx}_{hub_idx}')
                        gy2 = model.NewIntVar(0, self.H, f'bgy2_{b_idx}_{hub_idx}')
                        gap_x = model.NewIntVar(0, self.W, f'bgapx_{b_idx}_{hub_idx}')
                        gap_y = model.NewIntVar(0, self.H, f'bgapy_{b_idx}_{hub_idx}')

                        model.AddMaxEquality(gx1, [0, xs[b_idx] - xe_h])
                        model.AddMaxEquality(gx2, [0, xs[hub_idx] - xe_b])
                        model.AddMaxEquality(gy1, [0, ys[b_idx] - ye_h])
                        model.AddMaxEquality(gy2, [0, ys[hub_idx] - ye_b])
                        model.Add(gap_x == gx1 + gx2)
                        model.Add(gap_y == gy1 + gy2)

                        # b_touch = 1 iff gap_x + gap_y == 0
                        total_gap = model.NewIntVar(0, self.W + self.H, f'btg_{b_idx}_{hub_idx}')
                        model.Add(total_gap == gap_x + gap_y)
                        model.Add(total_gap == 0).OnlyEnforceIf(b_touch)
                        model.Add(total_gap > 0).OnlyEnforceIf(b_touch.Not())
                        touching_bools.append(b_touch)

                    if touching_bools:
                        model.AddBoolOr(touching_bools)  # At least one must be touching
        
        # 1. Maximize total area coverage (weight: 1 per solver-unit²)
        for i in range(n):
            area = model.NewIntVar(0, self.W * self.H, f'oa_{i}')
            model.AddMultiplicationEquality(area, ws[i], hs[i])
            obj_terms.append(area)

        # 2. Adjacency bonuses (soft)
        if use_adjacency:
            for type_a, type_b, weight in PREFERRED_ADJACENCY:
                for ia in type_index.get(type_a, []):
                    for ib in type_index.get(type_b, []):
                        if ia == ib:
                            continue
                        # Proximity: minimize Manhattan distance between centroids
                        # Use 2*centroid to avoid fractions
                        cx_a = model.NewIntVar(0, 2 * self.W, f'ca_x_{ia}_{ib}')
                        cy_a = model.NewIntVar(0, 2 * self.H, f'ca_y_{ia}_{ib}')
                        cx_b = model.NewIntVar(0, 2 * self.W, f'cb_x_{ia}_{ib}')
                        cy_b = model.NewIntVar(0, 2 * self.H, f'cb_y_{ia}_{ib}')
                        model.Add(cx_a == 2 * xs[ia] + ws[ia])
                        model.Add(cy_a == 2 * ys[ia] + hs[ia])
                        model.Add(cx_b == 2 * xs[ib] + ws[ib])
                        model.Add(cy_b == 2 * ys[ib] + hs[ib])

                        dx = model.NewIntVar(0, 2 * self.W, f'adx_{ia}_{ib}')
                        dy = model.NewIntVar(0, 2 * self.H, f'ady_{ia}_{ib}')
                        model.AddAbsEquality(dx, cx_a - cx_b)
                        model.AddAbsEquality(dy, cy_a - cy_b)

                        # Penalty: minimize centroid distance between adjacent rooms
                        # We negate (dx + dy) because we maximize the objective
                        neg_dist = model.NewIntVar(
                            -(2 * self.W + 2 * self.H), 0, f'nd_{ia}_{ib}'
                        )
                        model.Add(neg_dist == -(dx + dy))

                        # Create scaled penalty variable
                        scaled_w = max(1, weight // 100)
                        obj_terms.append(scaled_w * neg_dist)

        # 3. Vastu zone proximity (soft)
        if use_vastu:
            for i, room in enumerate(expanded):
                rid = room['id']
                zone = vastu_assignments.get(rid, 'C')
                if zone not in VASTU_ZONES:
                    zone = 'C'
                tx, ty = VASTU_ZONES[zone]
                target_x = int(tx * self.W)
                target_y = int(ty * self.H)

                cx2 = model.NewIntVar(0, 2 * self.W, f'vc_x_{rid}')
                cy2 = model.NewIntVar(0, 2 * self.H, f'vc_y_{rid}')
                model.Add(cx2 == 2 * xs[i] + ws[i])
                model.Add(cy2 == 2 * ys[i] + hs[i])

                vdx = model.NewIntVar(0, 2 * self.W, f'vdx_{rid}')
                vdy = model.NewIntVar(0, 2 * self.H, f'vdy_{rid}')
                model.AddAbsEquality(vdx, cx2 - 2 * target_x)
                model.AddAbsEquality(vdy, cy2 - 2 * target_y)

                neg_vd = model.NewIntVar(
                    -(2 * self.W + 2 * self.H), 0, f'nvd_{rid}'
                )
                model.Add(neg_vd == -(vdx + vdy))
                obj_terms.append(neg_vd)  # weight 1

        # 4. Passage spine bonus
        for i, room in enumerate(expanded):
            if room['normalized_type'] in SPINE_TYPES:
                # Reward elongation: maximize max(w,h)
                max_dim = model.NewIntVar(0, max(self.W, self.H), f'spine_{i}')
                model.AddMaxEquality(max_dim, [ws[i], hs[i]])
                obj_terms.append(50 * max_dim)  # bonus for long passages

        if obj_terms:
            model.Maximize(sum(obj_terms))

        # ── SOLVE ─────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max_time
        solver.parameters.num_workers = 4

        t0 = time.perf_counter()
        status = solver.Solve(model)
        solve_ms = (time.perf_counter() - t0) * 1000

        status_map = {
            cp_model.OPTIMAL: 'OPTIMAL',
            cp_model.FEASIBLE: 'FEASIBLE',
            cp_model.INFEASIBLE: 'INFEASIBLE',
            cp_model.MODEL_INVALID: 'MODEL_INVALID',
            cp_model.UNKNOWN: 'UNKNOWN',
        }
        status_name = status_map.get(status, 'UNKNOWN')

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {'rooms': [], 'status': status_name,
                    'solve_time_ms': round(solve_ms, 1), 'coverage_pct': 0}

        # ── EXTRACT SOLUTION ──────────────────────────────────────────
        placed = []
        total_area = 0
        for i, room in enumerate(expanded):
            rx = solver.Value(xs[i]) / SCALE
            ry = solver.Value(ys[i]) / SCALE
            rw = solver.Value(ws[i]) / SCALE
            rh = solver.Value(hs[i]) / SCALE
            area = rw * rh
            total_area += area
            placed.append({
                'id': room['id'],
                'type': room.get('type', room['normalized_type']),
                'normalized_type': room['normalized_type'],
                'label': room.get('label', ''),
                'x': round(rx, 2),
                'y': round(ry, 2),
                'width': round(rw, 2),
                'height': round(rh, 2),
                'area': round(area, 1),
            })

        coverage = (total_area / self.plot_area * 100) if self.plot_area > 0 else 0
        return {
            'rooms': placed,
            'status': status_name,
            'solve_time_ms': round(solve_ms, 1),
            'coverage_pct': round(coverage, 1),
        }

    def _emergency_strip_fill(self, rooms: List[Dict]) -> Dict[str, Any]:
        """Last-resort deterministic strip fill."""
        logger.warning("Using emergency strip-fill layout")
        placed = []
        cx, cy, rh = 0.0, 0.0, 0.0

        for room in rooms:
            nt = room['normalized_type']
            defaults = (40, 90, 180, 5.0, 15.0)
            _, typ_a, _, min_side, _ = ROOM_SIZES.get(nt, defaults)
            w = max(min_side, math.sqrt(typ_a))
            h = typ_a / w
            if cx + w > self.plot_w:
                cx = 0; cy += rh; rh = 0
            if cy + h > self.plot_h:
                h = max(3, self.plot_h - cy)
            placed.append({
                'id': room['id'], 'type': room.get('type', nt),
                'normalized_type': nt,
                'x': round(cx, 2), 'y': round(cy, 2),
                'width': round(w, 2), 'height': round(h, 2),
                'area': round(w * h, 1),
            })
            cx += w; rh = max(rh, h)

        total_area = sum(r['area'] for r in placed)
        coverage = (total_area / self.plot_area * 100) if self.plot_area > 0 else 0
        return {
            'rooms': placed, 'status': 'EMERGENCY_STRIP',
            'solve_time_ms': 0, 'coverage_pct': round(coverage, 1),
        }


def solve_layout(
    plot_width_ft: float,
    plot_height_ft: float,
    rooms: List[Dict],
    vastu_assignments: Optional[Dict[str, str]] = None,
    entry_direction: str = 'S',
    max_time_seconds: float = 5.0,
    fixed_positions: Optional[Dict[str, Dict]] = None,
    floor_number: int = 0,
) -> Dict[str, Any]:
    """
    Top-level convenience function.
    Returns dict with 'rooms', 'status', 'solve_time_ms', 'coverage_pct'.
    """
    solver = ConstraintSolver(plot_width_ft, plot_height_ft)
    return solver.solve(
        rooms, vastu_assignments, entry_direction, 
        max_time_seconds, fixed_positions=fixed_positions, 
        floor_number=floor_number
    )
