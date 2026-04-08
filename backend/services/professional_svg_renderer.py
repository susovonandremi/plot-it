"""
Professional SVG Blueprint Renderer - v2.0 (Shapely Geometry)
=============================================================
Renders architectural blueprints using **Shapely Polygon** geometry
for walls, rooms, and collision-free label placement.

Architecture (v2.0):
  Layer 1 (Walls):   Master Wall Boundary Polygon (via structural_engine's
                     ``generate_wall_boundary`` - Shapely boolean difference)
                     rendered as SVG <path> with solid black fill + optional
                     diagonal hatch pattern.  Thick stroke on exterior boundary.
  Layer 2 (Rooms):   Room Polygons rendered with thin light-gray stroke (1px).
  Layer 3 (Doors):   Arc symbols with wall breaks.
  Layer 4 (Windows): Triple-line symbols on exterior walls.
  Layer 5 (Labels):  Bounding-box collision check against wall boundary;
                     labels shifted towards room centroid until clear.
  Layer 6+:          Dimension lines, compass, scale bar, title block, etc.

Legacy 1D-line-segment wall extraction (``extract_wall_segments``,
``merge_collinear_walls``) is retained as a thin compatibility shim for
door/window placement but is **no longer used for visual wall rendering**.
"""
import logging

import math
import svgwrite
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from services.building_program import BuildingProgram, BuildingType

# ── Shapely (computational geometry for wall boundary + label collision) ──
from shapely.geometry import Polygon, box as shapely_box, mapping
from shapely.ops import unary_union
from services.structural_engine import generate_wall_boundary, WallBoundaryGeometry

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

WALL_THICKNESS = 0.5    # 6 inches in feet (standard residential)
DOOR_WIDTH = 3.0        # 3 feet standard interior door
WINDOW_WIDTH = 4.0      # 4 feet standard window
TOLERANCE = 0.15        # Coordinate tolerance for floating-point matching
INK_COLOR = "#000000"      # Professional Black (Blueprint Ink)
DIM_INK_COLOR = "#334155"  # Desaturated gray for secondary symbols
ROOM_FILL = "#FFFFFF"      # Pure white interiors for blueprints

# Floor material patterns mapped to room types
ROOM_FLOOR_MATERIALS = {
    'living':         'marble',
    'dining':         'marble',
    'bedroom':        'hardwood',
    'master_bedroom': 'hardwood',
    'bathroom':       'tile',
    'kitchen':        'tile',
    'pooja':          'marble',
    'study':          'hardwood',
    'verandah':       'terracotta',
    'balcony':        'terracotta',
    'courtyard':      'terracotta',
    'entrance':       'marble',
    'foyer':          'marble',
    'passage':        'concrete',
    'staircase':      'concrete',
}

ROOM_DISPLAY_NAMES = {
    'bedroom':        'BEDROOM',
    'master_bedroom': 'M. BEDROOM',
    'bathroom':       'BATH',
    'kitchen':        'KITCHEN',
    'dining':         'DINING',
    'living':         'LIVING ROOM',
    'pooja':          'POOJA',
    'study':          'STUDY',
    'garage':         'GARAGE',
    'entrance':       'ENTRANCE',
    'entry':          'ENTRY',
    'foyer':          'FOYER',
    'hallway':        'HALL',
    'passage':        'PASSAGE',
    'staircase':      'STAIRCASE',
    'lift':           'LIFT',
    'verandah':       'VER.',
    'balcony':        'BALCONY',
    'stair_room':     'MUMTY',
    'overhead_water_tank': 'OHT',
    'open_terrace':   'OPEN TERRACE',
}

# Rooms that get windows on exterior walls (used as fallback if no BuildingProgram)
WINDOW_ELIGIBLE = {'bedroom', 'master_bedroom', 'living', 'dining', 'kitchen', 'study'}


# ═══════════════════════════════════════════════════════════════════════
# WALL SEGMENT EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

def get_plot_bounds(placed_rooms: list) -> dict:
    """Compute the bounding box of the entire plot from rooms."""
    if not placed_rooms:
        return {'min_x': 0, 'min_y': 0, 'max_x': 0, 'max_y': 0}
    
    min_x = min(r['x'] for r in placed_rooms)
    min_y = min(r['y'] for r in placed_rooms)
    max_x = max(r['x'] + r['width'] for r in placed_rooms)
    max_y = max(r['y'] + r['height'] for r in placed_rooms)
    
    return {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}


def extract_wall_segments(placed_rooms: list, plot_bounds: dict = None, shape_config: dict = None) -> dict:
    """
    Converts room rectangles into deduplicated wall segments.
    
    Each room generates 4 walls (top/bottom/left/right).
    Walls shared between adjacent rooms are merged into one segment.
    Exterior walls (on plot boundary) are tagged separately.
    
    Returns:
        {
            'horizontal': [{'x1','y1','x2','y2','is_exterior','room_ids'}, ...],
            'vertical':   [{'x1','y1','x2','y2','is_exterior','room_ids'}, ...],
            'all':        combined list
        }
    """
    if plot_bounds is None:
        plot_bounds = get_plot_bounds(placed_rooms)
    
    horizontal_walls = []
    vertical_walls = []
    
    for room in placed_rooms:
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        rid = room.get('id', 'unknown')
        
        # Top wall (horizontal)
        horizontal_walls.append({
            'x1': x, 'y1': y, 'x2': x + w, 'y2': y,
            'room_ids': [rid]
        })
        # Bottom wall (horizontal)
        horizontal_walls.append({
            'x1': x, 'y1': y + h, 'x2': x + w, 'y2': y + h,
            'room_ids': [rid]
        })
        # Left wall (vertical)
        vertical_walls.append({
            'x1': x, 'y1': y, 'x2': x, 'y2': y + h,
            'room_ids': [rid]
        })
        # Right wall (vertical)
        vertical_walls.append({
            'x1': x + w, 'y1': y, 'x2': x + w, 'y2': y + h,
            'room_ids': [rid]
        })
    
    # Merge overlapping/adjacent segments on the same line
    horizontal_walls = merge_collinear_walls(horizontal_walls, axis='horizontal')
    vertical_walls = merge_collinear_walls(vertical_walls, axis='vertical')
    
    # Tag exterior vs interior
    min_x = plot_bounds['min_x']
    min_y = plot_bounds['min_y']
    max_x = plot_bounds['max_x']
    max_y = plot_bounds['max_y']
    
    def is_ext_horizontal(y, x_min, x_max):
        if not shape_config or shape_config.get('type') == 'rectangle':
            return abs(y - min_y) < TOLERANCE or abs(y - max_y) < TOLERANCE
        
        # L-Shape Logic (assume NE Cutout for now)
        if shape_config.get('type') in ['L_shape', 'l_shape']:
            cw = shape_config.get('cutout_width', 0)
            ch = shape_config.get('cutout_height', 0)
            # Default to NE if not specified? 
            # Or pass corner. Assuming NE.
            
            # Edges: y=min_y (Top Left), y=max_y (Bottom), y=min_y + ch (Inner Horizontal)
            if abs(y - max_y) < TOLERANCE: return True # Bottom is always ext
            if abs(y - min_y) < TOLERANCE and x_max <= (max_x - cw) + TOLERANCE: return True # Top Left part
            if abs(y - (min_y + ch)) < TOLERANCE and x_min >= (max_x - cw) - TOLERANCE: return True # Inner Horizontal
            
        return False

    def is_ext_vertical(x, y_min, y_max):
        if not shape_config or shape_config.get('type') == 'rectangle':
            return abs(x - min_x) < TOLERANCE or abs(x - max_x) < TOLERANCE
            
        # L-Shape Logic (NE Cutout)
        if shape_config.get('type') in ['L_shape', 'l_shape']:
            cw = shape_config.get('cutout_width', 0)
            ch = shape_config.get('cutout_height', 0)
            
            # Edges: x=min_x (Left), x=max_x (Bottom Right), x=max_x-cw (Inner Vertical)
            if abs(x - min_x) < TOLERANCE: return True
            if abs(x - max_x) < TOLERANCE and y_min >= (min_y + ch) - TOLERANCE: return True # Right part (lower)
            if abs(x - (max_x - cw)) < TOLERANCE and y_max <= (min_y + ch) + TOLERANCE: return True # Inner Vertical
            
        return False

    for wall in horizontal_walls:
        wall['is_exterior'] = is_ext_horizontal(wall['y1'], wall['x1'], wall['x2'])
    
    for wall in vertical_walls:
        wall['is_exterior'] = is_ext_vertical(wall['x1'], wall['y1'], wall['y2'])
    
    all_walls = horizontal_walls + vertical_walls
    
    return {
        'horizontal': horizontal_walls,
        'vertical': vertical_walls,
        'all': all_walls,
        'exterior': [w for w in all_walls if w.get('is_exterior', False)]
    }


def merge_collinear_walls(walls: list, axis: str) -> list:
    """
    Merges walls on the same line that overlap or touch.
    Removes duplicate walls where rooms share a boundary.
    Collects room_ids from merged walls.
    """
    if not walls:
        return []
    
    if axis == 'horizontal':
        walls.sort(key=lambda w: (round(w['y1'], 1), w['x1']))
    else:
        walls.sort(key=lambda w: (round(w['x1'], 1), w['y1']))
    
    merged = []
    current = {
        'x1': walls[0]['x1'], 'y1': walls[0]['y1'],
        'x2': walls[0]['x2'], 'y2': walls[0]['y2'],
        'room_ids': list(walls[0].get('room_ids', []))
    }
    
    for wall in walls[1:]:
        same_line = False
        adjacent = False
        
        if axis == 'horizontal':
            same_line = abs(wall['y1'] - current['y1']) < TOLERANCE
            adjacent = wall['x1'] <= current['x2'] + TOLERANCE
        else:
            same_line = abs(wall['x1'] - current['x1']) < TOLERANCE
            adjacent = wall['y1'] <= current['y2'] + TOLERANCE
        
        if same_line and adjacent:
            # Extend current wall
            if axis == 'horizontal':
                current['x2'] = max(current['x2'], wall['x2'])
            else:
                current['y2'] = max(current['y2'], wall['y2'])
            # Collect room IDs
            for rid in wall.get('room_ids', []):
                if rid not in current['room_ids']:
                    current['room_ids'].append(rid)
        else:
            merged.append(current)
            current = {
                'x1': wall['x1'], 'y1': wall['y1'],
                'x2': wall['x2'], 'y2': wall['y2'],
                'room_ids': list(wall.get('room_ids', []))
            }
    
    merged.append(current)
    return merged


# ═══════════════════════════════════════════════════════════════════════
# DOOR PLACEMENT
# ═══════════════════════════════════════════════════════════════════════

def find_shared_wall(room1: dict, room2: dict) -> Optional[dict]:
    """
    Finds the shared wall segment between two adjacent rooms.
    Returns None if rooms don't share a wall.
    """
    r1x, r1y = room1['x'], room1['y']
    r1w, r1h = room1['width'], room1['height']
    r2x, r2y = room2['x'], room2['y']
    r2w, r2h = room2['width'], room2['height']
    
    # Vertical shared wall: room1's right edge == room2's left edge (or vice versa)
    if abs((r1x + r1w) - r2x) < TOLERANCE:
        # Shared vertical wall at x = r1x + r1w
        y_start = max(r1y, r2y)
        y_end = min(r1y + r1h, r2y + r2h)
        if y_end - y_start > TOLERANCE:
            return {
                'x1': r1x + r1w, 'y1': y_start,
                'x2': r1x + r1w, 'y2': y_end,
                'orientation': 'vertical',
                'length': y_end - y_start
            }
    
    if abs((r2x + r2w) - r1x) < TOLERANCE:
        y_start = max(r1y, r2y)
        y_end = min(r1y + r1h, r2y + r2h)
        if y_end - y_start > TOLERANCE:
            return {
                'x1': r1x, 'y1': y_start,
                'x2': r1x, 'y2': y_end,
                'orientation': 'vertical',
                'length': y_end - y_start
            }
    
    # Horizontal shared wall: room1's bottom edge == room2's top edge (or vice versa)
    if abs((r1y + r1h) - r2y) < TOLERANCE:
        x_start = max(r1x, r2x)
        x_end = min(r1x + r1w, r2x + r2w)
        if x_end - x_start > TOLERANCE:
            return {
                'x1': x_start, 'y1': r1y + r1h,
                'x2': x_end, 'y2': r1y + r1h,
                'orientation': 'horizontal',
                'length': x_end - x_start
            }
    
    if abs((r2y + r2h) - r1y) < TOLERANCE:
        x_start = max(r1x, r2x)
        x_end = min(r1x + r1w, r2x + r2w)
        if x_end - x_start > TOLERANCE:
            return {
                'x1': x_start, 'y1': r1y,
                'x2': x_end, 'y2': r1y,
                'orientation': 'horizontal',
                'length': x_end - x_start
            }
    
    return None


def find_door_positions(placed_rooms: list, building_program: Optional[BuildingProgram] = None) -> list:
    """
    Places doors on shared walls between adjacent rooms.
    v2.5: Implements a 'one door per room' rule for circulation access to avoid 'too many doors'.
    """
    doors = []
    seen_pairs: Set[frozenset] = set()
    
    # Track rooms that already have a door to a circulation space
    # (passage, living, foyer, dining)
    has_circulation_access: Set[str] = set()
    
    CIRCULATION_HUBS = {'passage', 'hallway', 'foyer', 'living', 'dining', 'corridor'}
    
    # Sort rooms so circulation hubs are processed consistently
    rooms = sorted(placed_rooms, key=lambda r: r['id'])
    
    def norm(t):
        return t.lower().replace(' ', '_').replace('_room', '').replace('room', '')

    for i, room1 in enumerate(rooms):
        r1_id = room1['id']
        r1_type_orig = room1['type']
        r1_type = norm(r1_type_orig)
        is_r1_hub = r1_type in CIRCULATION_HUBS

        # Rule 3: For private rooms (bedroom, etc.), only allow ONE door to ANY circulation hub
        if not is_r1_hub and r1_id in has_circulation_access:
            # Special case: kitchen can have multiple (to dining and passage)
            if r1_type != 'kitchen':
                continue

        for room2 in rooms[i + 1:]:
            r2_id = room2['id']
            r2_type = norm(room2['type'])
            is_r2_hub = r2_type in CIRCULATION_HUBS
            
            pair_key = frozenset({r1_id, r2_id})
            if pair_key in seen_pairs:
                continue
            
            # --- DOOR FILTERING LOGIC ---
            # Rule 4: If a room already has a door to A circulation hub, don't add another door to ANOTHER hub segment
            if not is_r1_hub and is_r2_hub and r1_id in has_circulation_access and r1_type != 'kitchen':
                continue
            if is_r1_hub and not is_r2_hub and r2_id in has_circulation_access and r2_type != 'kitchen':
                continue

            # --- SMART BUDGET CHECK ---
            if building_program:
                door_config = building_program.should_place_door(r1_type, r2_type)
                if door_config is None:
                    continue
                door_width = door_config['width']
                door_type = door_config['type']
            else:
                # Fallback: check NO_DOOR_PAIRS
                type_pair = frozenset({r1_type, r2_type})
                from services.building_program import NO_DOOR_PAIRS as _NO_DOOR
                if type_pair in _NO_DOOR:
                    continue
                door_width = 3.0
                door_type = 'internal'
            
            shared = find_shared_wall(room1, room2)
            if shared is None:
                continue
            
            # Wall must be long enough for a door + margin
            if shared['length'] < door_width + 1.2:
                continue
            
            # --- RECORD PLACEMENT ---
            seen_pairs.add(pair_key)
            if not is_r1_hub and is_r2_hub: has_circulation_access.add(r1_id)
            if is_r1_hub and not is_r2_hub: has_circulation_access.add(r2_id)

            # Center the door on the shared wall
            if shared['orientation'] == 'vertical':
                door_x = shared['x1']
                door_y = (shared['y1'] + shared['y2']) / 2
            else:
                door_x = (shared['x1'] + shared['x2']) / 2
                door_y = shared['y1']
            
            doors.append({
                'room1_id': r1_id,
                'room2_id': r2_id,
                'room1_type': r1_type,
                'room2_type': r2_type,
                'wall_segment': shared,
                'position': {'x': door_x, 'y': door_y},
                'width': door_width,
                'orientation': shared['orientation'],
                'door_type': door_type,
            })
    
    return doors


def find_window_positions(placed_rooms: list, plot_bounds: dict,
                          building_program: Optional[BuildingProgram] = None) -> list:
    """
    Places windows on exterior walls of eligible rooms.
    
    If a BuildingProgram is provided, uses per-room window budgets.
    Otherwise, falls back to placing one window per eligible exterior wall.
    
    Smart rules:
    - Bedroom: 1 window (master: 2)
    - Living: 2 large windows  
    - Kitchen: 1 window
    - Bathroom: 1 ventilator (small)
    - Passage/staircase/lift: NO windows
    - Total: 6-10 for a typical 2000 sqft plan (not 10+)
    """
    windows = []
    
    for room in placed_rooms:
        rtype = room['type'].lower()
        
        # Get window budget for this room
        if building_program:
            budget = building_program.get_window_budget(rtype)
            max_windows = budget['count']
            win_width = budget['width']
            win_type = budget['type']
            if max_windows == 0:
                continue
        else:
            # Fallback: old behavior
            if rtype not in WINDOW_ELIGIBLE:
                continue
            max_windows = 99  # No limit in legacy mode
            win_width = WINDOW_WIDTH
            win_type = 'standard'
        
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        
        exterior_walls = []
        
        # Top wall on plot boundary
        if abs(y - plot_bounds['min_y']) < TOLERANCE and w > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y, 'x2': x + w, 'y2': y,
                'orientation': 'horizontal', 'side': 'top'
            })
        
        # Bottom wall on plot boundary
        if abs((y + h) - plot_bounds['max_y']) < TOLERANCE and w > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y + h, 'x2': x + w, 'y2': y + h,
                'orientation': 'horizontal', 'side': 'bottom'
            })
        
        # Left wall on plot boundary
        if abs(x - plot_bounds['min_x']) < TOLERANCE and h > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y, 'x2': x, 'y2': y + h,
                'orientation': 'vertical', 'side': 'left'
            })
        
        # Right wall on plot boundary
        if abs((x + w) - plot_bounds['max_x']) < TOLERANCE and h > win_width + 1.0:
            exterior_walls.append({
                'x1': x + w, 'y1': y, 'x2': x + w, 'y2': y + h,
                'orientation': 'vertical', 'side': 'right'
            })
        
        # Apply budget limit: only place up to max_windows
        windows_placed = 0
        for ew in exterior_walls:
            if windows_placed >= max_windows:
                break
            
            if ew['orientation'] == 'horizontal':
                cx = (ew['x1'] + ew['x2']) / 2
                cy = ew['y1']
            else:
                cx = ew['x1']
                cy = (ew['y1'] + ew['y2']) / 2
            
            windows.append({
                'room_id': room['id'],
                'room_type': rtype,
                'position': {'x': cx, 'y': cy},
                'width': win_width,
                'orientation': ew['orientation'],
                'side': ew['side'],
                'window_type': win_type,
            })
            windows_placed += 1
    
    return windows


# ═══════════════════════════════════════════════════════════════════════
# WALL BREAKING (FOR DOORS & WINDOWS)
# ═══════════════════════════════════════════════════════════════════════

def split_wall_at_opening(wall: dict, opening_pos: float, opening_width: float, axis: str) -> list:
    """
    Splits a wall segment into two at an opening (door/window).
    
    Args:
        wall: Wall segment dict with x1,y1,x2,y2
        opening_pos: Center position of the opening along the wall's axis
        opening_width: Width of the opening in feet
        axis: 'horizontal' or 'vertical'
    
    Returns:
        List of 0-2 wall segments (the parts before and after the gap)
    """
    half = opening_width / 2
    result = []
    
    if axis == 'horizontal':
        gap_start = opening_pos - half
        gap_end = opening_pos + half
        
        # Left segment (before gap)
        if gap_start > wall['x1'] + TOLERANCE:
            left = dict(wall)
            left['x2'] = gap_start
            result.append(left)
        
        # Right segment (after gap)
        if gap_end < wall['x2'] - TOLERANCE:
            right = dict(wall)
            right['x1'] = gap_end
            result.append(right)
    else:
        gap_start = opening_pos - half
        gap_end = opening_pos + half
        
        # Top segment (before gap)
        if gap_start > wall['y1'] + TOLERANCE:
            top = dict(wall)
            top['y2'] = gap_start
            result.append(top)
        
        # Bottom segment (after gap)
        if gap_end < wall['y2'] - TOLERANCE:
            bottom = dict(wall)
            bottom['y1'] = gap_end
            result.append(bottom)
    
    return result


def apply_openings_to_walls(wall_segments: dict, doors: list, windows: list) -> dict:
    """
    Breaks wall segments wherever doors or windows exist.
    Returns modified wall segments with gaps.
    """
    h_walls = list(wall_segments['horizontal'])
    v_walls = list(wall_segments['vertical'])
    
    # Process doors
    for door in doors:
        dx = door['position']['x']
        dy = door['position']['y']
        dw = door['width']
        
        if door['orientation'] == 'vertical':
            # Break vertical wall at door position
            new_v = []
            for wall in v_walls:
                if (abs(wall['x1'] - dx) < TOLERANCE and
                    wall['y1'] <= dy + TOLERANCE and
                    wall['y2'] >= dy - TOLERANCE):
                    # This wall contains the door - split it
                    new_v.extend(split_wall_at_opening(wall, dy, dw, 'vertical'))
                else:
                    new_v.append(wall)
            v_walls = new_v
        else:
            # Break horizontal wall at door position
            new_h = []
            for wall in h_walls:
                if (abs(wall['y1'] - dy) < TOLERANCE and
                    wall['x1'] <= dx + TOLERANCE and
                    wall['x2'] >= dx - TOLERANCE):
                    new_h.extend(split_wall_at_opening(wall, dx, dw, 'horizontal'))
                else:
                    new_h.append(wall)
            h_walls = new_h
    
    # Process windows
    for window in windows:
        wx = window['position']['x']
        wy = window['position']['y']
        ww = window['width']
        
        if window['orientation'] == 'vertical':
            new_v = []
            for wall in v_walls:
                if (abs(wall['x1'] - wx) < TOLERANCE and
                    wall['y1'] <= wy + TOLERANCE and
                    wall['y2'] >= wy - TOLERANCE):
                    new_v.extend(split_wall_at_opening(wall, wy, ww, 'vertical'))
                else:
                    new_v.append(wall)
            v_walls = new_v
        else:
            new_h = []
            for wall in h_walls:
                if (abs(wall['y1'] - wy) < TOLERANCE and
                    wall['x1'] <= wx + TOLERANCE and
                    wall['x2'] >= wx - TOLERANCE):
                    new_h.extend(split_wall_at_opening(wall, wx, ww, 'horizontal'))
                else:
                    new_h.append(wall)
            h_walls = new_h
    
    return {
        'horizontal': h_walls,
        'vertical': v_walls,
        'all': h_walls + v_walls,
        'exterior': [w for w in (h_walls + v_walls) if w.get('is_exterior', False)]
    }


# ═══════════════════════════════════════════════════════════════════════
# SVG RENDERING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def _define_floor_patterns(dwg) -> None:
    """Defines SVG <pattern> elements for floor materials."""
    # Marble - subtle diagonal veins
    marble = dwg.pattern(id="floor-marble", size=(12, 12), patternUnits="userSpaceOnUse")
    marble.add(dwg.rect(insert=(0, 0), size=(12, 12), fill="#F5F0EB"))
    marble.add(dwg.line(start=(0, 8), end=(12, 4), stroke="#E8E0D8", stroke_width=0.5, opacity=0.6))
    marble.add(dwg.line(start=(2, 12), end=(10, 0), stroke="#DDD5CC", stroke_width=0.3, opacity=0.4))
    dwg.defs.add(marble)

    # Hardwood - horizontal grain lines
    hardwood = dwg.pattern(id="floor-hardwood", size=(20, 6), patternUnits="userSpaceOnUse")
    hardwood.add(dwg.rect(insert=(0, 0), size=(20, 6), fill="#F5E6D3"))
    hardwood.add(dwg.line(start=(0, 3), end=(20, 3), stroke="#E8D5BE", stroke_width=0.4))
    hardwood.add(dwg.line(start=(0, 5.5), end=(20, 5.5), stroke="#E0CCAA", stroke_width=0.3))
    dwg.defs.add(hardwood)

    # Tile - grid pattern
    tile = dwg.pattern(id="floor-tile", size=(10, 10), patternUnits="userSpaceOnUse")
    tile.add(dwg.rect(insert=(0, 0), size=(10, 10), fill="#F0F4F8"))
    tile.add(dwg.line(start=(0, 0), end=(10, 0), stroke="#D0D8E0", stroke_width=0.3))
    tile.add(dwg.line(start=(0, 0), end=(0, 10), stroke="#D0D8E0", stroke_width=0.3))
    dwg.defs.add(tile)

    # Terracotta - square tiles with grout
    terracotta = dwg.pattern(id="floor-terracotta", size=(14, 14), patternUnits="userSpaceOnUse")
    terracotta.add(dwg.rect(insert=(0, 0), size=(14, 14), fill="#F5E0CC"))
    terracotta.add(dwg.rect(insert=(1, 1), size=(12, 12), fill="#EACDB5", rx=1))
    dwg.defs.add(terracotta)

    # Concrete - subtle speckle
    concrete = dwg.pattern(id="floor-concrete", size=(8, 8), patternUnits="userSpaceOnUse")
    concrete.add(dwg.rect(insert=(0, 0), size=(8, 8), fill="#F0F0F0"))
    concrete.add(dwg.circle(center=(2, 3), r=0.3, fill="#E0E0E0"))
    concrete.add(dwg.circle(center=(6, 7), r=0.2, fill="#D8D8D8"))
    dwg.defs.add(concrete)


def _define_hatch_patterns(dwg) -> None:
    """Defines SVG <pattern> elements for architectural wall hatching."""
    # Standard 4x4 diagonal hatch for masonry (Black Wall Hatch)
    wall_hatch = dwg.pattern(id="wall-hatch", size=(4, 4), patternUnits="userSpaceOnUse")
    wall_hatch.add(dwg.line(start=(0, 4), end=(4, 0), stroke="#000000", stroke_width=0.5))
    dwg.defs.add(wall_hatch)
    
    # Standard 8x8 wide diagonal hatch for Balcony/Terrace (Gray)
    terrace_hatch = dwg.pattern(id="terrace-hatch", size=(8, 8), patternUnits="userSpaceOnUse")
    terrace_hatch.add(dwg.line(start=(0, 8), end=(8, 0), stroke="#aaaaaa", stroke_width=0.5))
    dwg.defs.add(terrace_hatch)

    # Legacy Brick (retained for compatibility if needed)
    hatch_brick = dwg.pattern(id="hatch-brick", size=(8, 8), patternUnits="userSpaceOnUse")
    hatch_brick.add(dwg.line(start=(0, 8), end=(8, 0), stroke="#475569", stroke_width=0.75, opacity=0.4))
    dwg.defs.add(hatch_brick)
    
    # Concrete - stipple/speckle pattern
    hatch_concrete = dwg.pattern(id="hatch-concrete", size=(10, 10), patternUnits="userSpaceOnUse")
    hatch_concrete.add(dwg.circle(center=(2, 2), r=0.5, fill="#94A3B8", opacity=0.5))
    hatch_concrete.add(dwg.circle(center=(7, 4), r=0.4, fill="#64748B", opacity=0.6))
    hatch_concrete.add(dwg.circle(center=(4, 8), r=0.5, fill="#94A3B8", opacity=0.5))
    dwg.defs.add(hatch_concrete)
    
    # Cross-hatch for structural
    hatch_structural = dwg.pattern(id="hatch-structural", size=(10, 10), patternUnits="userSpaceOnUse")
    hatch_structural.add(dwg.line(start=(0, 0), end=(10, 10), stroke="#334155", stroke_width=0.5, opacity=0.3))
    hatch_structural.add(dwg.line(start=(0, 10), end=(10, 0), stroke="#334155", stroke_width=0.5, opacity=0.3))
    dwg.defs.add(hatch_structural)


def _define_shadow_filter(dwg) -> None:
    """Defines SVG <filter> for drop shadow depth effect."""
    shadow = dwg.defs.add(dwg.filter(id="room-shadow", x="-5%", y="-5%", width="115%", height="115%"))
    shadow.feGaussianBlur(in_="SourceAlpha", stdDeviation=2, result="blur")
    shadow.feOffset(in_="blur", dx=1.5, dy=1.5, result="offset")
    fc = shadow.feComponentTransfer(in_="offset", result="shadow")
    fc.feFuncA(type_="linear", slope=0.15)
    shadow.feMerge(["shadow", "SourceGraphic"])


# ═══════════════════════════════════════════════════════════════════════
# SHAPELY-BASED RENDERING - v2.0
# ═══════════════════════════════════════════════════════════════════════

def _polygon_to_svg_path(poly, scale, offset_x, offset_y) -> str:

    """
    Convert a Shapely Polygon (with possible holes) into an SVG ``d`` path
    string.  Coordinates are scaled and offset by *margin*.
    """
    parts: List[str] = []

    def _ring_to_d(ring, close: bool = True) -> str:
        coords = list(ring.coords)
        if not coords:
            return ""
        sx = offset_x + coords[0][0] * scale
        sy = offset_y + coords[0][1] * scale
        segs = [f"M {sx:.2f},{sy:.2f}"]
        for x, y in coords[1:]:
            segs.append(f"L {offset_x + x * scale:.2f},{offset_y + y * scale:.2f}")
        if close:
            segs.append("Z")
        return " ".join(segs)

    if poly.geom_type == "MultiPolygon":
        for geom in poly.geoms:
            parts.append(_ring_to_d(geom.exterior))
            for interior in geom.interiors:
                parts.append(_ring_to_d(interior))
    elif poly.geom_type == "Polygon":
        parts.append(_ring_to_d(poly.exterior))
        for interior in poly.interiors:
            parts.append(_ring_to_d(interior))
    else:
        return ""

    return " ".join(parts)


def _build_room_polygons(placed_rooms: List[Dict]) -> List[Polygon]:
    """Convert placed room dicts into a list of Shapely box polygons."""
    polys: List[Polygon] = []
    for room in placed_rooms:
        if room.get('is_annotation'):
            continue
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        if w > 0 and h > 0:
            polys.append(shapely_box(x, y, x + w, y + h))
    return polys


def _build_wall_boundary(
    placed_rooms: List[Dict],
    plot_width: float,
    plot_height: float,
    ext_thickness: float = 0.75,
    int_thickness: float = 0.375,
) -> WallBoundaryGeometry:
    """
    Convenience wrapper: builds room Shapely polygons + plot polygon,
    calls ``generate_wall_boundary`` from ``structural_engine`` with 
    Real Blueprint variable thickness logic.
    """
    room_polys = _build_room_polygons(placed_rooms)
    plot_poly = shapely_box(0, 0, plot_width, plot_height)
    return generate_wall_boundary(room_polys, plot_poly, ext_thickness, int_thickness)


def render_wall_boundary_polygon(wall_boundary, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=True):



    """
    **Draft Layer 1 - Walls** (Architectural v4.0).
    Renders the master Wall Boundary Polygon with masonry wall-hatch for professional output.
    """
    poly = wall_boundary.polygon
    if poly.is_empty:
        return

    d = _polygon_to_svg_path(poly, scale, offset_x, offset_y)
    if not d:
        return

    # CHANGE 4: Wall hatch pattern for professional blueprint
    # 1. Apply wall-hatch pattern to the representing wall area
    dwg.add(dwg.path(
        d=d,
        fill="url(#wall-hatch)",
        stroke="#000000",
        stroke_width=1,
        fill_rule="evenodd",
    ))


def render_room_polygons(placed_rooms, scale, offset_x, offset_y, dwg, clip_union=None):
    """
    **Draft Layer 2 - Room dividers & Flooring** (Architectural v4.0).
    Draws each room with white fill and black ink strokes.
    Now supports clipping against structural columns to create integrated pillar notches.
    """
    for room in placed_rooms:
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']
        
        rtype = room['type'].lower().replace(' ', '_').replace('_room', '')
        if rtype in ['staircase', 'lift', 'elevator', 'stair_room']:
            continue
            
        # 1. Build room polygon
        room_box = shapely_box(rx, ry, rx + rw, ry + rh)
        
        # 2. Subtract pillars if provided to create notches
        if clip_union:
            room_poly = room_box.difference(clip_union)
        else:
            room_poly = room_box
            
        if room_poly.is_empty:
            continue
            
        # 3. Choose fill Pattern
        fill_color = "white"
        if any(t in rtype for t in ['balcony', 'verandah', 'terrace', 'open_terrace']):
            fill_color = "url(#terrace-hatch)"
            
        dasharray = "5,5" if room.get('is_annotation') else "none"
        
        # 4. Generate SVG Path
        # Note: scale is applied inside _polygon_to_svg_path
        # BUT _polygon_to_svg_path already applies offset_x and offset_y
        d = _polygon_to_svg_path(room_poly, scale, offset_x, offset_y)
        
        dwg.add(dwg.path(
            d=d,
            fill=fill_color,
            stroke=INK_COLOR,
            stroke_width=1,
            stroke_dasharray=dasharray,
            fill_rule="evenodd"
        ))


def _shift_label_clear_of_walls(
    label_x: float,
    label_y: float,
    label_w: float,
    label_h: float,
    room_cx: float,
    room_cy: float,
    wall_boundary: Optional[WallBoundaryGeometry],
    scale: int,
    margin: int,
    max_iterations: int = 12,
) -> Tuple[float, float]:
    """
    High-aggression collision check.
    """
    if wall_boundary is None or wall_boundary.polygon.is_empty:
        return label_x, label_y

    wall_poly = wall_boundary.polygon

    for i in range(max_iterations):
        lx_ft = (label_x - offset_x) / scale
        ly_ft = (label_y - label_h - offset_y) / scale
        lw_ft = label_w / scale
        lh_ft = label_h / scale
        label_box = shapely_box(lx_ft, ly_ft, lx_ft + lw_ft, ly_ft + lh_ft)

        if not wall_poly.intersects(label_box):
            break

        if i < 4: # Move toward centroid
            target_x = offset_x + room_cx * scale
            target_y = offset_y + room_cy * scale
            label_x += (target_x - label_x) * 0.4
            label_y += (target_y - label_y) * 0.4
        else: # Jump away
            jumps = [(25, 0), (-25, 0), (0, 25), (0, -25), (20, 20), (-20, -20)]
            dx, dy = jumps[(i-4) % len(jumps)]
            label_x += dx
            label_y += dy

    return label_x, label_y

    return label_x, label_y


def render_room_fills(placed_rooms, scale, offset_x, offset_y, dwg, palette=None):



    """
    Layer 1: Base color fills for rooms + texture overlay + shadow filter.
    """
    if palette is None:
        palette = {}
    
    is_monochrome = palette.get('is_monochrome', False)
    if is_monochrome:
        # In CAD mode, we typically don't have room fills, just white background
        return

    default_fill = palette.get('room_fill_default', '#F8F9FA')
    
    for room in placed_rooms:
        x = offset_x + room['x'] * scale
        y = offset_y + room['y'] * scale
        w = room['width'] * scale
        h = room['height'] * scale
        
        rtype = room['type'].lower().replace(' ', '_')
        
        # Check palette first, then fallback to global constant
        fill = palette.get(f'room_fill_{rtype}', ROOM_COLORS.get(room['type'].lower(), default_fill))
        floor_material = ROOM_FLOOR_MATERIALS.get(rtype, None)
        
        # Base color fill
        dwg.add(dwg.rect(
            insert=(x, y), size=(w, h),
            fill=fill, stroke="none",
            filter="url(#room-shadow)"
        ))
        
        # Material texture overlay
        if floor_material:
            dwg.add(dwg.rect(
                insert=(x, y), size=(w, h),
                fill=f"url(#floor-{floor_material})",
                opacity=0.35, stroke="none"
            ))


def render_walls_with_junctions(wall_segments, scale, offset_x, offset_y, dwg, wall_color="#000000", use_hatching=False):



    """
    Layer 2: Thick solid wall shapes with proper T/L junctions.
    
    Walls are rendered as filled rectangles.
    - Exterior Walls: 9" thickness (0.75 ft), Solid Black (#000000)
    - Interior Walls: 4.5" thickness (0.375 ft), Dark Grey (#404040)
    
    Junctions are handled by overlapping - extending by half-thickness.
    """
    EXT_THICKNESS = 0.75  # 9 inches
    INT_THICKNESS = 0.375 # 4.5 inches
    
    EXT_COLOR = INK_COLOR 
    INT_COLOR = INK_COLOR 
    
    # Draw horizontal walls
    for wall in wall_segments['horizontal']:
        x1 = margin + wall['x1'] * scale
        x2 = margin + wall['x2'] * scale
        y_center = margin + wall['y1'] * scale
        
        is_ext = wall.get('is_exterior', False)
        
        # Determine properties
        thickness_ft = EXT_THICKNESS if is_ext else INT_THICKNESS
        thickness_px = thickness_ft * scale
        color = EXT_COLOR if is_ext else INT_COLOR
        half_t_px = thickness_px / 2
        
        # VERANDAH/BALCONY LOGIC:
        is_dashed = False
        if is_ext and len(wall['room_ids']) == 1:
            rid = wall['room_ids'][0].lower()
            if 'verandah' in rid or 'balcony' in rid:
                is_dashed = True
        
        if is_dashed:
            dwg.add(dwg.line(
                start=(x1, y_center),
                end=(x2, y_center),
                stroke=DIM_INK_COLOR,
                stroke_width=2,
                stroke_dasharray="5,5"
            ))
            continue
            
        # Extend by half-thickness at both ends for junction overlap
        x1_ext = x1 - half_t_px
        x2_ext = x2 + half_t_px
        
        # In hatching mode, we use heavy stroke and white fill to act as container for hatch
        fill_color = "white" if use_hatching else color
        stroke_w = 0.8 if use_hatching else 0.5

        dwg.add(dwg.rect(
            insert=(x1_ext, y_center - half_t_px),
            size=(x2_ext - x1_ext, thickness_px),
            fill=fill_color, stroke=color, stroke_width=stroke_w
        ))
        
    # Draw vertical walls
    for wall in wall_segments['vertical']:
        x_center = margin + wall['x1'] * scale
        y1 = margin + wall['y1'] * scale
        y2 = margin + wall['y2'] * scale
        
        is_ext = wall.get('is_exterior', False)
        
        thickness_ft = EXT_THICKNESS if is_ext else INT_THICKNESS
        thickness_px = thickness_ft * scale
        color = EXT_COLOR if is_ext else INT_COLOR
        half_t_px = thickness_px / 2
        
        is_dashed = False
        if is_ext and len(wall.get('room_ids', [])) == 1:
            rid = wall['room_ids'][0].lower()
            if 'verandah' in rid or 'balcony' in rid:
                is_dashed = True
        
        if is_dashed:
            dwg.add(dwg.line(
                start=(x_center, y1),
                end=(x_center, y2),
                stroke="#555",
                stroke_width=2,
                stroke_dasharray="5,5"
            ))
            continue

        y1_ext = y1 - half_t_px
        y2_ext = y2 + half_t_px
        
        fill_color = "white" if use_hatching else color
        stroke_w = 0.8 if use_hatching else 0.5
        
        dwg.add(dwg.rect(
            insert=(x_center - half_t_px, y1_ext),
            size=(thickness_px, y2_ext - y1_ext),
            fill=fill_color, stroke=color, stroke_width=stroke_w
        ))


def render_doors(doors, scale, offset_x, offset_y, dwg):



    """
    Layer 3: Door arcs showing swing direction.
    
    Each door is drawn as:
    - A quarter-circle arc (90°) showing swing direction
    - A thin line representing the door panel
    
    Main entry doors (D1) get:
    - Wider arc (3.5 ft), darker blue, thicker stroke
    - 'MAIN' label above the arc
    """
def draw_door_symbol(door_dict, scale, offset_x, offset_y, dwg) -> None:

    """
    Renders an architectural door symbol:
    1. Thin line for the door leaf (full width)
    2. Quarter-circle arc showing the swing path
    """
    dx_ft = door_dict['position']['x']
    dy_ft = door_dict['position']['y']
    dw_ft = door_dict['width']
    
    # Coordinates in canvas px
    dx = offset_x + dx_ft * scale
    dy = offset_y + dy_ft * scale
    dw = dw_ft * scale
    half_dw = dw / 2
    
    # Determine swing direction (simplified: swing into room2 by default, or avoid hub)
    # hub types are roughly: passage, hallway, foyer, living, dining
    CIRCULATION_HUBS = {'passage', 'hallway', 'foyer', 'living', 'dining', 'corridor'}
    r1_type = door_dict.get('room1_type', '').lower()
    r2_type = door_dict.get('room2_type', '').lower()
    
    # Swap if room1 is hub and room2 is not
    swing_into_r1 = (r2_type in CIRCULATION_HUBS and r1_type not in CIRCULATION_HUBS)
    
    color = "#000000" # All black for professional blueprint
    sw = 1
    
    if door_dict['orientation'] == 'horizontal':
        # Door on horizontal wall (top/bottom)
        # Leaf starts from one end of the opening
        leaf_x = dx - half_dw
        leaf_y_start = dy
        # Swing direction: Up (-1) or Down (1)
        # Default swing down (into room if room is below)
        dir_y = -1 if swing_into_r1 else 1 
        
        # 1. Door Leaf (Vertical line when open relative to wall)
        # Professional standard: 60-degree open leaf with NO arc for minimal clutter
        leaf_end_x = leaf_x + dw * 0.5 * (1 if dir_y == 1 else -1) # Offset slightly to show opening
        leaf_end_y = leaf_y_start + dw * dir_y
        
        # Draw straight leaf at 60 deg approx
        # For simplicity, we just draw the line at full width
        dwg.add(dwg.line(
            start=(leaf_x, leaf_y_start),
            end=(leaf_x + (dw * 0.5 * dir_y), leaf_y_start + (dw * 0.86 * dir_y)),
            stroke=color, stroke_width=sw
        ))
        
        # 2. Swing Arc REMOVED per user request
    else:
        # Door on vertical wall (left/right)
        leaf_x_start = dx
        leaf_y = dy - half_dw
        dir_x = -1 if swing_into_r1 else 1
        
        # 1. Door Leaf
        # Professional standard: 60-degree open leaf with NO arc for minimal clutter
        dwg.add(dwg.line(
            start=(leaf_x_start, leaf_y),
            end=(leaf_x_start + (dw * 0.86 * dir_x), leaf_y + (dw * 0.5 * dir_x)),
            stroke=color, stroke_width=sw
        ))
        
        # 2. Swing Arc REMOVED per user request

def render_doors(doors, scale, offset_x, offset_y, dwg):



    """Layer 4.1: Professional Door Symbols with ArcGIS-standard swing logic."""
    for door in doors:
        draw_door_symbol(door, scale, offset_x, offset_y, dwg)


def draw_window_symbol(win_dict, scale, offset_x, offset_y, dwg) -> None:

    """
    Renders an architectural window symbol:
    Three parallel lines across the wall thickness.
    """
    wx_ft = win_dict['position']['x']
    wy_ft = win_dict['position']['y']
    ww_ft = win_dict['width']
    
    # Wall thickness (Standard exterior 0.75ft = 9 inches)
    wt_ft = 0.75 
    
    wx = offset_x + wx_ft * scale
    wy = offset_y + wy_ft * scale
    ww = ww_ft * scale
    half_ww = ww / 2
    wt = wt_ft * scale
    half_wt = wt / 2
    
    color = INK_COLOR
    sw = 1
    
    if win_dict['orientation'] == 'horizontal':
        # Window on horizontal wall
        # 3 Parallel lines: top-edge, center, bottom-edge
        for dy in [-half_wt, 0, half_wt]:
            dwg.add(dwg.line(
                start=(wx - half_ww, wy + dy),
                end=(wx + half_ww, wy + dy),
                stroke=color, stroke_width=sw
            ))
    else:
        # Window on vertical wall
        # 3 Parallel lines: left-edge, center, right-edge
        for dx in [-half_wt, 0, half_wt]:
            dwg.add(dwg.line(
                start=(wx + dx, wy - half_ww),
                end=(wx + dx, wy + half_ww),
                stroke=color, stroke_width=sw
            ))

def render_windows(windows, scale, offset_x, offset_y, dwg):



    """Layer 4.2: Professional Window Symbols with triple-line glass indicators."""
    for win in windows:
        draw_window_symbol(win, scale, offset_x, offset_y, dwg)


def draw_staircase(room, scale, offset_x, offset_y, dwg) -> None:


    """
    Renders an architectural staircase symbol:
    1. Parallel tread lines (10px spacing)
    2. Directional UP arrow with arrowhead
    3. UP text label
    4. Structural 1.5px boundary (no fill)
    """
    sx = offset_x + room['x'] * scale
    sy = offset_y + room['y'] * scale
    sw = room['width'] * scale
    sh = room['height'] * scale
    
    color = INK_COLOR
    
    # Boundary: No fill, thick stroke for structural distinction
    dwg.add(dwg.rect(insert=(sx, sy), size=(sw, sh), fill="none", stroke=color, stroke_width=1.5))
    
    # Determine tread direction: treads are parallel lines across the 'width'
    # horizontal treads if taller than wide (h > w)
    if sh > sw:
        # Treads run horizontally (left-to-right)
        tread_depth_ft = 0.83 # 10 inches spacing
        tread_depth_px = tread_depth_ft * scale
        num_treads = max(2, int(sh / tread_depth_px))
        for i in range(1, num_treads):
            pos_y = sy + i * (sh / num_treads)
            dwg.add(dwg.line(start=(sx, pos_y), end=(sx + sw, pos_y), stroke=color, stroke_width=0.7))
            
        # UP arrow in middle pointing upward
        ax = sx + sw / 2
        dwg.add(dwg.line(start=(ax, sy + sh - 5), end=(ax, sy + 10), stroke=color, stroke_width=1))
        # Arrowhead at top
        dwg.add(dwg.polygon(points=[(ax - 3, sy + 10), (ax + 3, sy + 10), (ax, sy + 4)], fill=color))
        # UP text
        dwg.add(dwg.text("UP", insert=(ax + 5, sy + sh / 2), font_size="7px", font_family="Arial", fill=color))
        
    else:
        # Treads run vertically (top-to-bottom)
        tread_width_ft = 0.83
        tread_width_px = tread_width_ft * scale
        num_treads = max(2, int(sw / tread_width_px))
        for i in range(1, num_treads):
            pos_x = sx + i * (sw / num_treads)
            dwg.add(dwg.line(start=(pos_x, sy), end=(pos_x, sy + sh), stroke=color, stroke_width=0.7))
            
        # UP arrow in middle pointing rightward (default direction for horizontal rooms)
        ay = sy + sh / 2
        dwg.add(dwg.line(start=(sx + 5, ay), end=(sx + sw - 10, ay), stroke=color, stroke_width=1))
        # Arrowhead at right
        dwg.add(dwg.polygon(points=[(sx + sw - 10, ay - 3), (sx + sw - 10, ay + 3), (sx + sw - 4, ay)], fill=color))
        # UP text
        dwg.add(dwg.text("UP", insert=(sx + sw / 2, ay - 5), text_anchor="middle", font_size="7px", font_family="Arial", fill=color))



def _is_over_door_swing(tx, ty, label_text, doors, scale, offset_x, offset_y):
    margin = offset_x # Legacy shim
    # Avoid door arcs aggressively
    if not doors:
        return False
        
    for d in doors:
        pos = d.get('position', {})
        dx = offset_x + pos.get('x', 0) * scale
        dy = offset_y + pos.get('y', 0) * scale
        # 12ft clearance for passage labels, 8ft for others
        is_passage = "PASSAGE" in label_text.upper()
        clearance = 12.0 if is_passage else 8.0
        
        if abs(tx - dx) < clearance * scale and abs(ty - dy) < clearance * scale:
            return True
    return False


def render_room_labels(placed_rooms, scale, offset_x, offset_y, dwg,
                       palette=None, wall_boundary=None, doors=None, original_unit_system=None, is_roof=False):
    margin = offset_x # Legacy shim
    """
    v2.4: Ultra-compact labels + Door avoidance.
    """
    if palette is None: palette = {}
    text_color = INK_COLOR
    dim_color = "#475569"
    font_main = "Inter, sans-serif"

    placed_text_boxes = []
    
    # Pre-populate with door swing zones to avoid them
    if doors:
        for d in doors:
            pos = d.get('position', {})
            dx = offset_x + pos.get('x', 0) * scale
            dy = offset_y + pos.get('y', 0) * scale
            placed_text_boxes.append([dx - 14, dy - 14, 28, 28])

    def _get_bbox(x, y, text, size_px, anchor='middle'):
        w = len(str(text)) * 0.7 * size_px + 4
        h = size_px * 1.5
        if anchor == 'middle': return [x - w/2, y - h*0.75, w, h]
        return [x, y - h*0.75, w, h]

    def _is_overlapping(new_box):
        for box in placed_text_boxes:
            if not (new_box[0] + new_box[2] < box[0] - 1 or 
                    new_box[0] > box[0] + box[2] + 1 or 
                    new_box[1] + new_box[3] < box[1] - 1 or 
                    new_box[1] > box[1] + box[3] + 1):
                return True
        return False

    for room in placed_rooms:
        r_w_px = room['width'] * scale
        r_h_px = room['height'] * scale
        cx = offset_x + room['x'] * scale + r_w_px / 2
        cy = offset_y + room['y'] * scale + r_h_px / 2
        
        # Center in feet for wall boundary checks
        room_cx_ft = room['x'] + room['width'] / 2
        room_cy_ft = room['y'] + room['height'] / 2
        
        room_sqft = room['width'] * room['height']
        rtype = room['type'].lower()
        
        # PROFESSIONAL STANDARD: Suppress habitable labels on Roof
        if is_roof and rtype not in ['stair_room', 'overhead_water_tank', 'open_terrace', 'solar_panel']:
            continue
        
        rid = room.get('id', rtype)
        parts = rid.rsplit('_', 1)
        suffix = parts[1] if len(parts) > 1 and parts[1].isdigit() else ''
        base_name = ROOM_DISPLAY_NAMES.get(rtype, rtype.upper())
        
        if room['width'] < 8.0: 
            base_name = {'MASTER BEDROOM': 'M.B.', 'BEDROOM': 'BED', 'LIVING ROOM': 'LIV.', 'BATHROOM': 'BTH', 'STAIRCASE': 'STR', 'ENTRANCE': 'E'}.get(base_name, base_name)
        display_name = f"{base_name} {suffix}".strip() if suffix else base_name
        
        # --- DRASITC FONT REDUCTION ---
        if room_sqft < 40: font_px = 6
        elif room_sqft < 100: font_px = 7.5
        else: font_px = 9.5 

        est_w = len(display_name) * 0.7 * font_px
        if est_w > r_w_px * 0.85 and font_px > 5:
            font_px = max(5, int(font_px * (r_w_px * 0.8) / est_w))

        name_x, name_y = cx, cy - 2
        current_font_px = font_px
        show_secondary = room['width'] > 4.5 and room_sqft > 25

        for shift_i in range(12): # More attempts
            name_size_str = f"{current_font_px}px"
            dim_size_str = f"{max(5.5, current_font_px - 1)}px"
            name_bbox = _get_bbox(name_x, name_y, display_name, current_font_px)
            
            w_ft, h_ft = int(room['width']), int(room['height'])
            dim_text = f"{w_ft}'{int(round((room['width']-w_ft)*12))}\"x{h_ft}'{int(round((room['height']-h_ft)*12))}\""
            dim_y = name_y + current_font_px + 2
            dim_bbox = _get_bbox(name_x, dim_y, dim_text, max(5.5, current_font_px - 1))

            if _is_overlapping(name_bbox) or (show_secondary and _is_overlapping(dim_bbox)) or _is_over_door_swing(name_x, name_y, display_name, doors, scale, offset_x, offset_y):
                name_y += 18
                if shift_i > 0: name_x += (15 if shift_i % 2 == 0 else -15) 
                if shift_i == 3: show_secondary = False
                if shift_i >= 6: current_font_px = max(5, int(current_font_px * 0.8))
                continue
            
            if wall_boundary:
                test_x, test_y = _shift_label_clear_of_walls(
                    name_bbox[0], name_bbox[1] + name_bbox[3], name_bbox[2], name_bbox[3],
                    room_cx_ft, room_cy_ft, wall_boundary, scale, margin
                )
                if abs(test_y - (name_bbox[1] + name_bbox[3])) > 1 or abs(test_x - name_bbox[0]) > 1:
                    name_x, name_y = test_x + name_bbox[2]/2, test_y
                    name_bbox = _get_bbox(name_x, name_y, display_name, current_font_px)
                    if _is_overlapping(name_bbox): continue
            
            dwg.add(dwg.text(display_name, insert=(name_x, name_y), text_anchor="middle",
                             font_size=name_size_str, font_family=font_main, font_weight="700",
                             fill=text_color, letter_spacing="-0.2px"))
            placed_text_boxes.append(name_bbox)
            
            if show_secondary:
                dwg.add(dwg.text(dim_text, insert=(name_x, dim_y), text_anchor="middle",
                                 font_size=dim_size_str, font_family="JetBrains Mono, monospace",
                                 fill=dim_color))
                placed_text_boxes.append(dim_bbox)
            break


def render_dimension_lines(dwg, placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, original_unit_system=None):



    """
    Layer 5: External dimension lines with arrow terminators.
    
    Draws dimension lines along the plot boundary edges:
    - Bottom edge: room widths
    - Right edge: room heights
    - Overall plot dimensions
    """
    if palette is None: palette = {}
    is_monochrome = palette.get('is_monochrome', False)
    
    DIM_OFFSET = 20      # Distance from wall to dimension line (px)
    ARROW_SIZE = 5       # Arrow head size
    DIM_COLOR = "#FFFFFF" 
    
    # ── Overall plot width (bottom) ──────────────────────────
    plot_x_start = margin
    plot_x_end = margin + plot_width * scale
    dim_y = offset_y + plot_height * scale + DIM_OFFSET + 25
    
    _draw_dim_line(dwg, plot_x_start, dim_y, plot_x_end, dim_y,
                   _fmt_feet_inches(plot_width), ARROW_SIZE, DIM_COLOR, 'horizontal')
    
    # ── Overall plot height (right) ──────────────────────────
    plot_y_start = margin
    plot_y_end = margin + plot_height * scale
    dim_x = offset_x + plot_width * scale + DIM_OFFSET + 25
    
    _draw_dim_line(dwg, dim_x, plot_y_start, dim_x, plot_y_end,
                   _fmt_feet_inches(plot_height), ARROW_SIZE, DIM_COLOR, 'vertical')
    
    # ── Per-room dimensions along bottom edge ────────────────
    bottom_rooms = sorted(
        [r for r in placed_rooms if abs(r['y'] + r['height'] - plot_height) < TOLERANCE],
        key=lambda r: r['x']
    )
    
    dim_y_rooms = margin + plot_height * scale + DIM_OFFSET
    for room in bottom_rooms:
        x1 = offset_x + room['x'] * scale
        x2 = margin + (room['x'] + room['width']) * scale
        _draw_dim_line(dwg, x1, dim_y_rooms, x2, dim_y_rooms,
                       _fmt_feet_inches(room['width']), ARROW_SIZE - 1, DIM_COLOR, 'horizontal',
                       font_size="9px")
    
    # ── Per-room dimensions along right edge ─────────────────
    right_rooms = sorted(
        [r for r in placed_rooms if abs(r['x'] + r['width'] - plot_width) < TOLERANCE],
        key=lambda r: r['y']
    )
    
    dim_x_rooms = margin + plot_width * scale + DIM_OFFSET
    for room in right_rooms:
        y1 = offset_y + room['y'] * scale
        y2 = margin + (room['y'] + room['height']) * scale
        _draw_dim_line(dwg, dim_x_rooms, y1, dim_x_rooms, y2,
                       _fmt_feet_inches(room['height']), ARROW_SIZE - 1, DIM_COLOR, 'vertical',
                       font_size="9px")


def _fmt_feet_inches(feet: float) -> str:
    """Converts decimal feet to feet-inches format: 11'-7\" """
    ft = int(feet)
    inches = int(round((feet - ft) * 12))
    if inches == 12:
        ft += 1
        inches = 0
    if inches == 0:
        return f"{ft}'-0\""
    return f"{ft}'-{inches}\""


def _draw_dim_line(dwg, x1, y1, x2, y2, label, arrow_size, color, orientation,
                   font_size="10px") -> None:
    """
    Draws a dimension line with architectural ticks (diagonal slashes) and centered label.
    """
    tick_size = 4
    extension = 2  # Extend dimension line slightly past the witness line
    
    if orientation == 'horizontal':
        length = x2 - x1
        if length < 20:
            return  # Too small
        
        # Main line (extended)
        dwg.add(dwg.line(
            start=(x1 - extension, y1), end=(x2 + extension, y1),
            stroke=color, stroke_width=0.75
        ))
        
        # Diagonal Ticks ( / )
        # Start
        dwg.add(dwg.line(
            start=(x1 - tick_size, y1 + tick_size),
            end=(x1 + tick_size, y1 - tick_size),
            stroke=color, stroke_width=1.5
        ))
        # End
        dwg.add(dwg.line(
            start=(x2 - tick_size, y1 + tick_size),
            end=(x2 + tick_size, y1 - tick_size),
            stroke=color, stroke_width=1.5
        ))
        
        # Witness lines (small vertical extensions at ends) - Optional, 
        # usually handled by the caller extending lines to this point. 
        # But here we assume x1,y1 is the intersection.
        
        # Label (Above the line)
        mid_x = (x1 + x2) / 2
        dwg.add(dwg.text(
            label,
            insert=(mid_x, y1 - 4),
            text_anchor="middle",
            font_size=font_size,
            font_family="JetBrains Mono, monospace",
            # font_weight="500",
            fill=color
        ))
        
    else: # vertical
        length = y2 - y1
        if length < 20:
            return
            
        # Main line (extended)
        dwg.add(dwg.line(
            start=(x1, y1 - extension), end=(x1, y2 + extension),
            stroke=color, stroke_width=0.75
        ))
        
        # Diagonal Ticks ( / )
        dwg.add(dwg.line(
            start=(x1 - tick_size, y1 + tick_size),
            end=(x1 + tick_size, y1 - tick_size),
            stroke=color, stroke_width=1.5
        ))
        dwg.add(dwg.line(
            start=(x1 - tick_size, y2 + tick_size),
            end=(x1 + tick_size, y2 - tick_size),
            stroke=color, stroke_width=1.5
        ))
        
        # Label (Rotated, to the Left of the line)
        mid_y = (y1 + y2) / 2
        # Position left of line: x1 - 4
        # Rotate -90? Or 90?
        # Standard: Read from Right -> Text runs Up. Bottom of letters towards line.
        # If I rotate -90, text runs Up. Bottom of letters faces Left (away from line).
        # If I rotate 90 (sim to existing code), text runs Down?
        # Let's try rotate(-90).
        # Or standard "Reading Up": rotate(-90).
        
        dwg.add(dwg.text(
            label,
            insert=(x1 - 6, mid_y),
            text_anchor="middle",
            font_size=font_size,
            font_family="JetBrains Mono, monospace",
            fill=color,
            transform=f"rotate(-90, {x1 - 6}, {mid_y})"
        ))


def render_compass_rose(canvas_width: int, dwg) -> None:
    """Compass rose in top-right corner."""
    cx = canvas_width - 65
    cy = 55
    
    dwg.add(dwg.circle(center=(cx, cy), r=28, fill="white",
                        stroke="#1E293B", stroke_width=2.5))
    dwg.add(dwg.circle(center=(cx, cy), r=22, fill="none",
                        stroke="#CBD5E1", stroke_width=1))
    
    # North arrow (red)
    dwg.add(dwg.polygon(
        points=[(cx, cy - 18), (cx - 6, cy + 2), (cx + 6, cy + 2)],
        fill="#DC2626", stroke="#1E293B", stroke_width=1.5
    ))
    # South indicator
    dwg.add(dwg.polygon(
        points=[(cx, cy + 18), (cx - 6, cy - 2), (cx + 6, cy - 2)],
        fill="#64748B", stroke="#1E293B", stroke_width=1.5
    ))
    
    labels = [("N", cx, cy - 35, "#DC2626", "13px", "700"),
              ("S", cx, cy + 42, "#64748B", "10px", "600"),
              ("E", cx + 35, cy + 5, "#64748B", "10px", "600"),
              ("W", cx - 35, cy + 5, "#64748B", "10px", "600")]
    
    for text, tx, ty, color, size, weight in labels:
        dwg.add(dwg.text(text, insert=(tx, ty), text_anchor="middle",
                          font_size=size, font_family="Archivo, sans-serif",
                          font_weight=weight, fill=color))


def render_scale_bar(margin: int, canvas_height: int, scale: int, dwg) -> None:
    """Scale bar in bottom-left."""
    sx = margin
    sy = canvas_height - 35
    sl = 10 * scale
    
    dwg.add(dwg.line(start=(sx, sy), end=(sx + sl, sy), stroke="#1E293B", stroke_width=3))
    
    for i in [0, 5, 10]:
        tx = sx + i * scale
        dwg.add(dwg.line(start=(tx, sy - 6), end=(tx, sy + 6), stroke="#1E293B", stroke_width=2))
    
    for label, lx in [("0", sx), ("5'", sx + 5 * scale), ("10'", sx + sl)]:
        dwg.add(dwg.text(label, insert=(lx, sy + 22), text_anchor="middle",
                          font_size="11px", font_family="JetBrains Mono, monospace",
                          fill="#64748B"))
    
    dwg.add(dwg.text("SCALE", insert=(sx + sl / 2, sy - 15), text_anchor="middle",
                      font_size="9px", font_family="Archivo, sans-serif",
                      font_weight="600", fill="#94A3B8", letter_spacing="1px"))


def render_vastu_badge(vastu_score: dict, margin: int, dwg) -> None:
    """Vastu score badge in top-left."""
    bx, by = margin, 25
    
    color_map = {
        'green': '#16A34A', 'yellow': '#CA8A04',
        'orange': '#EA580C', 'red': '#DC2626'
    }
    badge_color = color_map.get(vastu_score.get('color', 'green'), '#64748B')
    
    dwg.add(dwg.rect(insert=(bx, by), size=(200, 35), rx=8, ry=8,
                      fill=badge_color, opacity=0.95))
    
    text = f"Vastu: {vastu_score.get('score', 0)}% • {vastu_score.get('label', 'Unknown')}"
    dwg.add(dwg.text(text, insert=(bx + 100, by + 23), text_anchor="middle",
                      font_size="13px", font_family="Archivo, sans-serif",
                      font_weight="600", fill="white"))


def render_watermark(canvas_width: int, canvas_height: int, user_tier: str, dwg) -> None:
    """Watermark for free tier."""
    if user_tier != "free":
        return
    
    wx = canvas_width - 165
    wy = canvas_height - 25
    
    dwg.add(dwg.rect(insert=(wx - 8, wy - 18), size=(160, 24), rx=5, ry=5,
                      fill="white", opacity=0.85))
    dwg.add(dwg.text("PlotAI.com · Free Plan", insert=(wx, wy),
                      font_size="12px", font_family="Inter, sans-serif",
                      font_weight="500", fill="#64748B"))


def render_title_block(plot_area: float, vastu_score: dict, scale, offset_x, offset_y, dwg, canvas_width: int, canvas_height: int,

                       plot_width: float = 0, plot_height: float = 0,
                       floor_label: str = "FLOOR PLAN",
                       building_program: Optional[BuildingProgram] = None) -> None:
    """
    Upgrade 2: Full-width title block at the bottom of the SVG.
    
    Height: 80px, full canvas width.
    Left:   Project name, "FLOOR PLAN" subtitle, plot dimensions, total area.
    Center: Scale indicator, Vastu score.
    Right:  "Generated by PlotAI", date, small north arrow.
    Top border: 3px solid line separating from the plan.
    """
    BLOCK_HEIGHT = 80
    block_y = canvas_height - BLOCK_HEIGHT
    
    # --- Background ---
    dwg.add(dwg.rect(
        insert=(0, block_y), size=(canvas_width, BLOCK_HEIGHT),
        fill="white", stroke="none"
    ))
    
    # --- Top border (3px) ---
    dwg.add(dwg.line(
        start=(0, block_y), end=(canvas_width, block_y),
        stroke="#1A1A2E", stroke_width=3
    ))
    
    # --- Vertical dividers ---
    left_w = canvas_width * 0.40
    center_w = canvas_width * 0.30
    # right section = remaining
    
    dwg.add(dwg.line(
        start=(left_w, block_y + 8), end=(left_w, block_y + BLOCK_HEIGHT - 8),
        stroke="#E2E8F0", stroke_width=1
    ))
    dwg.add(dwg.line(
        start=(left_w + center_w, block_y + 8),
        end=(left_w + center_w, block_y + BLOCK_HEIGHT - 8),
        stroke="#E2E8F0", stroke_width=1
    ))
    
    # ── LEFT SECTION: Project info ──
    lx = 16
    ly = block_y + 22
    
    # Project name
    project_name = "RESIDENTIAL FLOOR PLAN"
    if building_program:
        meta = building_program.get_metadata()
        btype = meta.get('building_type', 'independent_house').replace('_', ' ').upper()
        project_name = btype
    
    dwg.add(dwg.text(project_name, insert=(lx, ly),
                      font_size="14px", font_family="Archivo, sans-serif",
                      font_weight="700", fill="#1A1A2E", letter_spacing="1px"))
    
    # Subtitle
    dwg.add(dwg.text(floor_label, insert=(lx, ly + 16),
                      font_size="10px", font_family="Archivo, sans-serif",
                      font_weight="600", fill="#64748B", letter_spacing="1px"))
    
    # Plot dimensions
    dim_text = f"Plot: {_fmt_feet_inches(plot_width)} × {_fmt_feet_inches(plot_height)}"
    dwg.add(dwg.text(dim_text, insert=(lx, ly + 32),
                      font_size="9px", font_family="JetBrains Mono, monospace",
                      fill="#94A3B8"))
    
    # Total area
    area_text = f"Area: {plot_area:.0f} sqft"
    dwg.add(dwg.text(area_text, insert=(lx + 200, ly + 32),
                      font_size="9px", font_family="JetBrains Mono, monospace",
                      fill="#94A3B8"))
    
    # ── CENTER SECTION: Scale & Vastu ──
    cx = left_w + center_w / 2
    cy = block_y + 28
    
    scale_ratio = f"1:{int(120 / scale)}" if scale > 0 else "1:12"
    dwg.add(dwg.text(f"SCALE  {scale_ratio}", insert=(cx, cy),
                      text_anchor="middle", font_size="12px",
                      font_family="JetBrains Mono, monospace",
                      font_weight="400", fill="#1E293B"))
    
    vastu_text = f"Vastu: {vastu_score.get('score', 0)}% · {vastu_score.get('label', '')}"
    color_map = {
        'green': '#16A34A', 'yellow': '#CA8A04',
        'orange': '#EA580C', 'red': '#DC2626'
    }
    v_color = color_map.get(vastu_score.get('color', 'green'), '#64748B')
    dwg.add(dwg.text(vastu_text, insert=(cx, cy + 22),
                      text_anchor="middle", font_size="10px",
                      font_family="Inter, sans-serif",
                      font_weight="600", fill=v_color))
    
    # ── RIGHT SECTION: Credits, date, north arrow ──
    rx = left_w + center_w + 16
    ry = block_y + 22
    
    dwg.add(dwg.text("Generated by PlotAI", insert=(rx, ry),
                      font_size="11px", font_family="Inter, sans-serif",
                      font_weight="500", fill="#1E293B"))
    
    date_str = datetime.now().strftime("%d %b %Y")
    dwg.add(dwg.text(date_str, insert=(rx, ry + 18),
                      font_size="9px", font_family="JetBrains Mono, monospace",
                      fill="#94A3B8"))
    
    # Small north arrow in right section
    arrow_x = canvas_width - 40
    arrow_y = block_y + BLOCK_HEIGHT / 2
    # Arrow body
    dwg.add(dwg.line(start=(arrow_x, arrow_y + 12), end=(arrow_x, arrow_y - 12),
                      stroke="#DC2626", stroke_width=1.5))
    # Arrowhead
    dwg.add(dwg.polygon(
        points=[(arrow_x, arrow_y - 15), (arrow_x - 4, arrow_y - 8), (arrow_x + 4, arrow_y - 8)],
        fill="#DC2626"
    ))
    dwg.add(dwg.text("N", insert=(arrow_x, arrow_y - 18),
                      text_anchor="middle", font_size="8px",
                      font_family="Archivo, sans-serif", font_weight="700",
                      fill="#DC2626"))


# ═══════════════════════════════════════════════════════════════════════
# ARCHITECTURAL ELEMENT RENDERERS
# ═══════════════════════════════════════════════════════════════════════

# --- DUPLICATE REMOVED ---




def render_floor_label(floor_label: str, canvas_width: int, plot_height: float,
                       scale, offset_x, offset_y, dwg) -> None:
    """
    Renders the floor plan title below the drawing.
    
    E.g., "GROUND FLOOR PLAN" or "3RD FLOOR PLAN"
    Centered below the plot boundary.
    """
    y_pos = (plot_height * scale) + margin + 160
    
    dwg.add(dwg.text(
        floor_label,
        insert=(canvas_width / 2, y_pos),
        text_anchor="middle",
        font_size="16px",
        font_family="Archivo, sans-serif",
        font_weight="700",
        fill="#1A1A2E",
        letter_spacing="3px"
    ))
    
    # Decorative underline
    label_width = len(floor_label) * 9
    dwg.add(dwg.line(
        start=(canvas_width / 2 - label_width / 2, y_pos + 6),
        end=(canvas_width / 2 + label_width / 2, y_pos + 6),
        stroke="#1A1A2E", stroke_width=1.5
    ))


# ═══════════════════════════════════════════════════════════════════════
# UPGRADE 1: WALL HATCHING
# ═══════════════════════════════════════════════════════════════════════

def _define_hatch_patterns(dwg) -> None:
    """
    Defines SVG <pattern> elements for wall hatching in <defs>.
    
    Two patterns:
    - hatch-brick: single diagonal lines (exterior walls)
    - hatch-concrete: crossed diagonals (interior walls)
    Both at 3px spacing, 45° angle.
    """
    HATCH_SPACING = 3
    HATCH_COLOR = "#555555"
    HATCH_STROKE = 0.4

    # --- Brick pattern (single diagonal) ---
    brick = dwg.pattern(id="hatch-brick", size=(HATCH_SPACING, HATCH_SPACING),
                        patternUnits="userSpaceOnUse",
                        patternTransform="rotate(45)")
    brick.add(dwg.line(start=(0, 0), end=(0, HATCH_SPACING),
                       stroke=HATCH_COLOR, stroke_width=HATCH_STROKE))
    dwg.defs.add(brick)

    # --- Concrete pattern (crossed diagonals) ---
    concrete = dwg.pattern(id="hatch-concrete", size=(HATCH_SPACING, HATCH_SPACING),
                           patternUnits="userSpaceOnUse",
                           patternTransform="rotate(45)")
    concrete.add(dwg.line(start=(0, 0), end=(0, HATCH_SPACING),
                          stroke=HATCH_COLOR, stroke_width=HATCH_STROKE))
    concrete.add(dwg.line(start=(0, 0), end=(HATCH_SPACING, 0),
                          stroke=HATCH_COLOR, stroke_width=HATCH_STROKE))
    dwg.defs.add(concrete)


def draw_wall_hatch(wall_segments: dict, scale, offset_x, offset_y, dwg) -> None:

    """
    Upgrade 1: Fills wall polygons with diagonal hatching.
    
    Exterior walls → brick pattern (single diagonal).
    Interior walls → concrete pattern (crossed diagonals).
    Each hatch rect is clipped to the wall polygon boundary.
    """
    EXT_THICKNESS = 0.75
    INT_THICKNESS = 0.375

    clip_counter = [0]  # mutable counter for unique clip IDs

    def _hatch_rect(x, y, w, h, is_exterior):
        clip_counter[0] += 1
        clip_id = f"wall-clip-{clip_counter[0]}"

        clip = dwg.defs.add(dwg.clipPath(id=clip_id))
        clip.add(dwg.rect(insert=(x, y), size=(w, h)))

        pattern_url = "url(#hatch-brick)" if is_exterior else "url(#hatch-concrete)"
        rect = dwg.rect(insert=(x, y), size=(w, h),
                         fill=pattern_url, stroke="none",
                         clip_path=f"url(#{clip_id})")
        dwg.add(rect)

    # Horizontal walls
    for wall in wall_segments['horizontal']:
        is_ext = wall.get('is_exterior', False)
        # Skip dashed verandah/balcony walls
        if is_ext and len(wall.get('room_ids', [])) == 1:
            rid = wall['room_ids'][0].lower()
            if 'verandah' in rid or 'balcony' in rid:
                continue

        thickness_ft = EXT_THICKNESS if is_ext else INT_THICKNESS
        thickness_px = thickness_ft * scale
        half_t = thickness_px / 2

        x1 = margin + wall['x1'] * scale - half_t
        x2 = margin + wall['x2'] * scale + half_t
        y_center = margin + wall['y1'] * scale

        _hatch_rect(x1, y_center - half_t, x2 - x1, thickness_px, is_ext)

    # Vertical walls
    for wall in wall_segments['vertical']:
        is_ext = wall.get('is_exterior', False)
        if is_ext and len(wall.get('room_ids', [])) == 1:
            rid = wall['room_ids'][0].lower()
            if 'verandah' in rid or 'balcony' in rid:
                continue

        thickness_ft = EXT_THICKNESS if is_ext else INT_THICKNESS
        thickness_px = thickness_ft * scale
        half_t = thickness_px / 2

        x_center = margin + wall['x1'] * scale
        y1 = margin + wall['y1'] * scale - half_t
        y2 = margin + wall['y2'] * scale + half_t

        _hatch_rect(x_center - half_t, y1, thickness_px, y2 - y1, is_ext)


# ═══════════════════════════════════════════════════════════════════════
# UPGRADE 3: SMART DOOR PLACEMENT
# ═══════════════════════════════════════════════════════════════════════

def adjust_door_positions(doors: list, placed_rooms: list) -> list:
    """
    Post-processes door list to:
    1. Avoid placing doors within 2ft of wall corners/junctions.
    2. Prefer bedroom→bathroom walls and kitchen→living/dining walls.
    
    Does NOT modify wall merging or junction logic - only shifts door center
    positions within their existing wall segments.
    """
    CORNER_CLEARANCE = 2.0  # feet

    # Build room lookup
    room_map = {r['id']: r for r in placed_rooms}

    for door in doors:
        wall = door['wall_segment']
        w_start = wall['y1'] if wall['orientation'] == 'vertical' else wall['x1']
        w_end = wall['y2'] if wall['orientation'] == 'vertical' else wall['x2']
        wall_length = w_end - w_start

        # Current center position along the wall axis
        pos_key = 'y' if wall['orientation'] == 'vertical' else 'x'
        current_center = door['position'][pos_key]

        half_door = door['width'] / 2

        # Compute clear zone: [wall_start + clearance, wall_end - clearance]
        clear_start = w_start + CORNER_CLEARANCE
        clear_end = w_end - CORNER_CLEARANCE

        # If clear zone is too small, just center the door
        if clear_end - clear_start < door['width']:
            new_center = (w_start + w_end) / 2
        else:
            # Clamp door center to clear zone
            new_center = max(clear_start + half_door,
                             min(current_center, clear_end - half_door))

        door['position'][pos_key] = new_center

    # --- Room-type preference: re-pick walls for bedrooms and kitchens ---
    # This works by checking if there is a better wall for bedroom→bathroom
    # or kitchen→living/dining adjacencies.
    # We iterate doors and for bedrooms with bathroom neighbors, check if
    # the door is already on the bathroom wall. If not and a bathroom wall
    # exists among the doors, we don't add a duplicate - we just note the
    # preference was already handled by the door placement rules.
    # (The existing should_place_door logic already gates which pairs get doors,
    #  so preference here is about the corner-avoidance shift direction.)

    for door in doors:
        r1_type = door.get('room1_type', '')
        r2_type = door.get('room2_type', '')

        # Bedroom doors: when adjacent to bathroom, shift closer to bathroom center
        if 'bedroom' in r1_type or 'bedroom' in r2_type:
            bath_id = None
            bed_id = None
            if 'bathroom' in r2_type:
                bath_id = door['room2_id']
                bed_id = door['room1_id']
            elif 'bathroom' in r1_type:
                bath_id = door['room1_id']
                bed_id = door['room2_id']

            if bath_id and bath_id in room_map:
                bath_room = room_map[bath_id]
                wall = door['wall_segment']
                # Nudge 0.5ft toward bathroom center (subtle preference)
                if wall['orientation'] == 'vertical':
                    bath_cy = bath_room['y'] + bath_room['height'] / 2
                    shift = 0.5 if bath_cy > door['position']['y'] else -0.5
                    door['position']['y'] += shift
                else:
                    bath_cx = bath_room['x'] + bath_room['width'] / 2
                    shift = 0.5 if bath_cx > door['position']['x'] else -0.5
                    door['position']['x'] += shift

        # Kitchen doors: shift toward living/dining side
        if 'kitchen' in r1_type or 'kitchen' in r2_type:
            living_id = None
            if r2_type in ('living', 'dining'):
                living_id = door['room2_id']
            elif r1_type in ('living', 'dining'):
                living_id = door['room1_id']

            if living_id and living_id in room_map:
                living_room = room_map[living_id]
                wall = door['wall_segment']
                if wall['orientation'] == 'vertical':
                    living_cy = living_room['y'] + living_room['height'] / 2
                    shift = 0.5 if living_cy > door['position']['y'] else -0.5
                    door['position']['y'] += shift
                else:
                    living_cx = living_room['x'] + living_room['width'] / 2
                    shift = 0.5 if living_cx > door['position']['x'] else -0.5
                    door['position']['x'] += shift

    return doors


# ═══════════════════════════════════════════════════════════════════════
# UPGRADE 4: SITE CONTEXT LAYER
# ═══════════════════════════════════════════════════════════════════════

def _draw_tree_symbol(dwg, cx: float, cy: float, radius: float = 6) -> None:
    """Draws a simplified tree symbol (plan view) - circle with radial lines."""
    # Canopy (green circle)
    dwg.add(dwg.circle(
        center=(cx, cy), r=radius,
        fill='#A8D5A0', stroke='#6B9E64', stroke_width=0.4, opacity=0.5
    ))
    # Trunk dot in center
    dwg.add(dwg.circle(
        center=(cx, cy), r=1.5,
        fill='#8B7355', stroke='none', opacity=0.6
    ))


def draw_site_context(placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, dwg, building_program=None):

    """Draws contextual elements AROUND the building footprint."""
    px, py = offset_x, offset_y
    pw, ph = plot_width * scale, plot_height * scale
    SETBACK = 5.0
    sb = SETBACK * scale  # Setback in pixels
    SETBACK_COLOR = "#000000"
    ROAD_COLOR = "#F1F5F9"
    ROAD_LABEL_COLOR = "#64748B"
    ROAD_WIDTH = 25.0
    GATE_WIDTH = 10.0
    GATE_COLOR = "#475569"
    
    # Building boundary in pixels for tree clipping
    # We use a rough box for garden exclusion
    bx1, by1 = 9999, 9999
    bx2, by2 = -9999, -9999
    for r in placed_rooms:
        rx, ry = px + r['x'] * scale, py + r['y'] * scale
        rw, rh = r['width'] * scale, r['height'] * scale
        bx1 = min(bx1, rx)
        by1 = min(by1, ry)
        bx2 = max(bx2, rx + rw)
        by2 = max(by2, ry + rh)

    tree_r = 5.0
    step = 20.0
    
    # --- 1. Yard & Garden (Trees along setbacks) ---
    for tx in range(int(px + sb), int(px + pw - sb), int(step)):
        if tx < bx1 - tree_r * 2 or tx > bx2 + tree_r * 2:
            _draw_tree_symbol(dwg, tx, py + sb / 2, tree_r * 0.8)
            _draw_tree_symbol(dwg, tx, py + ph - sb / 2, tree_r * 0.8)
            
    for ty in range(int(py + sb + step), int(py + ph - sb), int(step)):
        if ty < by1 - tree_r * 2 or ty > by2 + tree_r * 2:
            _draw_tree_symbol(dwg, px + sb / 2, ty, tree_r * 0.8)
            _draw_tree_symbol(dwg, px + pw - sb / 2, ty, tree_r * 0.8)

    # --- 2. Setback lines (dashed, 5ft inside plot boundary) ---
    if sb * 2 < pw and sb * 2 < ph:
        dwg.add(dwg.rect(
            insert=(px + sb, py + sb),
            size=(pw - 2 * sb, ph - 2 * sb),
            fill="none",
            stroke=SETBACK_COLOR,
            stroke_width=1,
            stroke_dasharray="4,3"
        ))
        # Setback label
        dwg.add(dwg.text(
            f"{SETBACK:.0f}' SETBACK",
            insert=(px + sb + 5, py + sb - 3),
            font_size='6px', font_family='Inter, sans-serif',
            font_weight='400', fill=SETBACK_COLOR, opacity=0.7
        ))

    # --- 3. Road indicator and gate ---
    # Determine entry side
    entry_side = 'bottom'  # default
    if building_program:
        entry_side = building_program.get_entry_wall_side()

    road_offset = 12  # px outside plot boundary

    # Find entry room center for gate position
    entrance = next(
        (r for r in placed_rooms
         if r['type'].lower() in ['entrance', 'main_door', 'entry', 'foyer']),
        None
    )

    if entry_side == 'bottom':
        road_y = py + ph + road_offset
        # Road line
        dwg.add(dwg.line(start=(px - 20, road_y), end=(px + pw + 20, road_y),
                         stroke=ROAD_COLOR, stroke_width=ROAD_WIDTH))
        # Road label
        dwg.add(dwg.text("ROAD", insert=(px + pw / 2, road_y + 14),
                         text_anchor="middle", font_size="8px",
                         font_family="Archivo, sans-serif", font_weight="600",
                         fill=ROAD_COLOR, letter_spacing="2px"))
        # Gate
        if entrance:
            gx = offset_x + (entrance['x'] + entrance['width'] / 2) * scale
        else:
            gx = px + pw / 2
        _draw_gate(dwg, gx, py + ph, gx, road_y, 'vertical', GATE_COLOR)

    elif entry_side == 'top':
        road_y = py - road_offset
        dwg.add(dwg.line(start=(px - 20, road_y), end=(px + pw + 20, road_y),
                         stroke=ROAD_COLOR, stroke_width=ROAD_WIDTH))
        dwg.add(dwg.text("ROAD", insert=(px + pw / 2, road_y - 6),
                         text_anchor="middle", font_size="8px",
                         font_family="Archivo, sans-serif", font_weight="600",
                         fill=ROAD_COLOR, letter_spacing="2px"))
        if entrance:
            gx = offset_x + (entrance['x'] + entrance['width'] / 2) * scale
        else:
            gx = px + pw / 2
        _draw_gate(dwg, gx, road_y, gx, py, 'vertical', GATE_COLOR)

    elif entry_side == 'left':
        road_x = px - road_offset
        dwg.add(dwg.line(start=(road_x, py - 20), end=(road_x, py + ph + 20),
                         stroke=ROAD_COLOR, stroke_width=ROAD_WIDTH))
        dwg.add(dwg.text("ROAD", insert=(road_x - 6, py + ph / 2),
                         text_anchor="middle", font_size="8px",
                         font_family="Archivo, sans-serif", font_weight="600",
                         fill=ROAD_COLOR, letter_spacing="2px",
                         transform=f"rotate(-90, {road_x - 6}, {py + ph / 2})"))
        if entrance:
            gy = offset_y + (entrance['y'] + entrance['height'] / 2) * scale
        else:
            gy = py + ph / 2
        _draw_gate(dwg, road_x, gy, px, gy, 'horizontal', GATE_COLOR)

    elif entry_side == 'right':
        road_x = px + pw + road_offset
        dwg.add(dwg.line(start=(road_x, py - 20), end=(road_x, py + ph + 20),
                         stroke=ROAD_COLOR, stroke_width=ROAD_WIDTH))
        dwg.add(dwg.text("ROAD", insert=(road_x + 6, py + ph / 2),
                         text_anchor="middle", font_size="8px",
                         font_family="Archivo, sans-serif", font_weight="600",
                         fill=ROAD_COLOR, letter_spacing="2px",
                         transform=f"rotate(90, {road_x + 6}, {py + ph / 2})"))
        if entrance:
            gy = offset_y + (entrance['y'] + entrance['height'] / 2) * scale
        else:
            gy = py + ph / 2
        _draw_gate(dwg, px + pw, gy, road_x, gy, 'horizontal', GATE_COLOR)


def _draw_gate(dwg, x1, y1, x2, y2, orientation, color) -> None:
    """
    Draws a small gate symbol: two perpendicular ticks with a gap between.
    (x1,y1) = plot boundary point, (x2,y2) = road point.
    """
    GATE_WIDTH = 8  # px half-width of gate ticks
    TICK_LEN = 5    # px

    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2

    if orientation == 'vertical':
        # Gate on top/bottom edge: two horizontal ticks
        dwg.add(dwg.line(start=(mid_x - GATE_WIDTH, y1),
                         end=(mid_x - GATE_WIDTH, y1 - TICK_LEN),
                         stroke=color, stroke_width=2))
        dwg.add(dwg.line(start=(mid_x + GATE_WIDTH, y1),
                         end=(mid_x + GATE_WIDTH, y1 - TICK_LEN),
                         stroke=color, stroke_width=2))
        # Dashed path between gate posts
        dwg.add(dwg.line(start=(mid_x - GATE_WIDTH, y1),
                         end=(mid_x + GATE_WIDTH, y1),
                         stroke=color, stroke_width=1.5,
                         stroke_dasharray="3,2"))
    else:
        # Gate on left/right edge: two vertical ticks
        dwg.add(dwg.line(start=(x1, mid_y - GATE_WIDTH),
                         end=(x1 - TICK_LEN, mid_y - GATE_WIDTH),
                         stroke=color, stroke_width=2))
        dwg.add(dwg.line(start=(x1, mid_y + GATE_WIDTH),
                         end=(x1 - TICK_LEN, mid_y + GATE_WIDTH),
                         stroke=color, stroke_width=2))
        dwg.add(dwg.line(start=(x1, mid_y - GATE_WIDTH),
                         end=(x1, mid_y + GATE_WIDTH),
                         stroke=color, stroke_width=1.5,
                         stroke_dasharray="3,2"))


# ═══════════════════════════════════════════════════════════════════════
# FURNITURE SVG RENDERING
# ═══════════════════════════════════════════════════════════════════════

def render_furniture_symbols(items, scale, offset_x, offset_y, dwg, parent_group=None):



    """
    Renders furniture items as simplified architectural plan-view symbols.
    Each item is drawn as a light gray rectangle with a label.
    """
    FURNITURE_COLORS = {
        'bed': '#D4C5A9',
        'wardrobe': '#C8B898',
        'sofa': '#C5B8A5',
        'table_rect': '#BFB199',
        'table_small': '#BFB199',
        'table_chairs': '#BFB199',
        'tv_unit': '#A89880',
        'counter_l': '#B8A888',
        'appliance': '#A0A0A0',
        'toilet': 'none',
        'basin': 'none',
        'shower': 'none',
        'desk': '#C5B8A5',
        'chair': '#BFB199',
        'shelf': '#C8B898',
        'altar': '#E8D5B5',
    }
    
    for item in items:
        x = offset_x + item['x'] * scale
        y = offset_y + item['y'] * scale
        w = item['width'] * scale
        h = item['height'] * scale
        
        container = parent_group if parent_group is not None else dwg
        color = FURNITURE_COLORS.get(item['symbol'], '#C8C0B0')
        
        # Furniture outline
        container.add(dwg.rect(
            insert=(x, y), size=(w, h),
            fill=color, stroke='#8B7355',
            stroke_width=0.5, rx=1, opacity=0.6
        ))
        
        # Special symbols for specific furniture types
        if item['symbol'] == 'bed':
            # Pillow indicator (small rectangle at top)
            pillow_h = min(h * 0.15, 8)
            container.add(dwg.rect(
                insert=(x + 2, y + 2), size=(w - 4, pillow_h),
                fill='#E8DCC8', stroke='#A89880', stroke_width=0.3, rx=2
            ))
        elif item['symbol'] == 'sofa':
            # Back cushion (thick line on one side)
            container.add(dwg.rect(
                insert=(x, y), size=(w, min(h * 0.25, 6)),
                fill='#B0A090', stroke='none', rx=1
            ))
        elif item['symbol'] == 'toilet':
            # Circle for toilet bowl
            cx = x + w / 2
            cy = y + h * 0.6
            container.add(dwg.ellipse(
                center=(cx, cy), r=(w * 0.35, h * 0.25),
                fill='white', stroke='#8B7355', stroke_width=0.5
            ))
        elif item['symbol'] == 'shower':
            # Shower tray with drain
            container.add(dwg.circle(
                center=(x + w / 2, y + h / 2), r=2,
                fill='#90B8C8', stroke='#708898', stroke_width=0.3
            ))
        
        # Label (only if piece is large enough)
        if w > 20 and h > 12:
            container.add(dwg.text(
                item['label'],
                insert=(x + w / 2, y + h / 2 + 3),
                text_anchor='middle', font_size='6px',
                font_family='Inter, sans-serif', font_weight='400',
                fill='#6B5B45', opacity=0.8
            ))


# ═══════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ═══════════════════════════════════════════════════════════════════════

def render_blueprint_professional(
    placement_data: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    vastu_score: Dict[str, Any],
    user_tier: str = "free",
    original_unit_system: Optional[Dict[str, Any]] = None,
    heavy_elements: Optional[List[Dict[str, Any]]] = None,
    building_program: Optional[BuildingProgram] = None,
    floor_number: int = 0,
    shape_config: Optional[Dict[str, Any]] = None,
    style_metadata: Optional[dict] = None,
    furniture_items: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Professional-grade SVG renderer with wall-segment architecture.
    
    Rendering layers (back to front):
    0.  Plot Boundary (White background + Property Layout)
    0.5 Site Context (setbacks, road, gate, yard fill)
    1.  Room fills (light pastels)
    2.  Walls (thick black with junction overlap - NO GAPS)
    2b. Wall hatching (brick/concrete patterns clipped to walls)
    3.  Doors (arc symbols with wall breaks, smart placement)
    4.  Windows (triple-line symbols with wall breaks)
    5.  Architectural elements (staircase treads, lift shaft cross)
    6.  Room labels + dimensions (feet-inches)
    7.  External dimension lines with arrows
    8.  Floor plan label ("GROUND FLOOR PLAN")
    9.  Compass rose
    10. Scale bar
    11. Vastu score badge
    12. Title block (full-width bottom bar)
    13. Watermark (free tier)
    
    Args:
        placement_data: List of placed room dicts from BSP engine
        plot_width: Plot width in feet
        plot_height: Plot height in feet
        vastu_score: Vastu scoring dict
        user_tier: 'free' or 'paid'
        building_program: Optional BuildingProgram for smart door/window placement
        shape_config: Optional dict defining plot shape
        style_metadata: Optional dict containing styling information like color_palette.
    
    Returns:
        SVG string
    """
    # --- DYNAMIC SCALING & VIEWBOX (v4.0) ---
    if not placement_data:
        return ""

    # 1. Find min/max bounds of all placed rooms to determine plan extent
    min_x = min(r['x'] for r in placement_data)
    min_y = min(r['y'] for r in placement_data)
    max_x = max(r['x'] + r['width'] for r in placement_data)
    max_y = max(r['y'] + r['height'] for r in placement_data)

    plan_width_ft = max_x - min_x
    plan_height_ft = max_y - min_y

    # Constants for professional CAD layout
    SCALE = 30.0           # 30 pixels per foot
    PADDING_PX = 80.0      # Fixed pixel margin on all sides
    TITLE_HEIGHT_PX = 120.0 # Fixed pixel height for title block

    # 2. Pre-shift approach: shift all rooms and elements once before any rendering
    shifted_rooms = []
    for r in placement_data:
        sr = dict(r)
        sr['x'] = round(r['x'] - min_x, 4)
        sr['y'] = round(r['y'] - min_y, 4)
        shifted_rooms.append(sr)

    # Detection for ROOF plan (Architectural standard: different visibility for roof/terrace)
    is_roof = any(r.get('type') in ['open_terrace', 'overhead_water_tank', 'lift_machine_room', 'mumty'] for r in shifted_rooms)

    # Shift structural columns if present
    shifted_columns = []
    if heavy_elements and 'columns' in heavy_elements:
        for col in heavy_elements['columns']:
            sc = dict(col)
            sc['x'] = round(col['x'] - min_x, 4)
            sc['y'] = round(col['y'] - min_y, 4)
            shifted_columns.append(sc)

    # 3. Calculate Canvas size based on ACTUAL plan extents plus fixed margins
    plan_width_px = plan_width_ft * SCALE
    plan_height_px = plan_height_ft * SCALE

    vb_w = plan_width_px + 2 * PADDING_PX
    vb_h = plan_height_px + 2 * PADDING_PX + TITLE_HEIGHT_PX

    dwg = svgwrite.Drawing(size=('100%', '100%'), profile='full')
    dwg.viewbox(0, 0, vb_w, vb_h)
    dwg.attribs['preserveAspectRatio'] = "xMidYMid meet"

    # Set offsets to land the shifted plan at the padding margin
    offset_x = PADDING_PX
    offset_y = PADDING_PX
    
    # Google Fonts
    dwg.defs.add(dwg.style("""
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap');
        .toggle-layer { /* Progressive disclosure layers */ }
    """))
    
    # Define hatch patterns for wall hatching (Upgrade 1)
    _define_hatch_patterns(dwg)
    
    # Define floor material patterns (v3.0)
    _define_floor_patterns(dwg)
    
    # Define shadow filter (v3.0)
    _define_shadow_filter(dwg)
    
    # ── LAYER 0: PLOT BOUNDARY ───────────────────────────────
    # We use the plan extent for the boundary to ensure it fits the Tight ViewBox
    plot_bounds = {
        'min_x': 0, 'min_y': 0,
        'max_x': plan_width_ft, 'max_y': plan_height_ft
    }
    
    if shape_config and shape_config.get('type') in ['L_shape', 'l_shape']:
        # Draw L-Shape Polygon
        w = plot_width
        d = plot_height
        cw = shape_config.get('cutout_width', 0)
        ch = shape_config.get('cutout_height', 0)
        
        # Points (Assuming NE Cutout)
        # Coordinate path: Top-Left -> Top-Mid -> Inner-Corner -> Right-Mid -> Bottom-Right -> Bottom-Left
        p0 = (0, 0)
        p1 = ((w-cw)*SCALE, 0)
        p2 = ((w-cw)*SCALE, ch*SCALE)
        p3 = (w*SCALE, ch*SCALE)
        p4 = (w*SCALE, d*SCALE)
        p5 = (0, d*SCALE)
        
        # Apply Margin
        points = []
        for p in [p0, p1, p2, p3, p4, p5]:
             points.append((p[0] + offset_x, p[1] + offset_y))
             
        dwg.add(dwg.polygon(
            points=points,
            fill="none",
            stroke="#000000",
            stroke_width=2,
            stroke_dasharray="10,5"
        ))
    else:
        # Standard Rectangle Property Line (Tight fit to plan)
        dwg.add(dwg.rect(
            insert=(offset_x, offset_y),
            size=(plan_width_ft * SCALE, plan_height_ft * SCALE),
            fill="none", 
            stroke="#000000",
            stroke_width=2,
            stroke_dasharray="10,5"
        ))
    
    # ── PREPARE DATA ─────────────────────────────────────────

    # ── v2.0: Build Shapely wall boundary polygon ────────────
    # Use shifted data and plan extents
    wall_boundary = _build_wall_boundary(shifted_rooms, plan_width_ft, plan_height_ft)

    # Legacy wall segments (retained as shim for door/window placement)
    wall_segments = extract_wall_segments(shifted_rooms, plot_bounds, shape_config)
    
    # Find doors and windows (with smart budgets if building_program provided)
    doors = find_door_positions(shifted_rooms, building_program)
    
    # Upgrade 3: Smart door placement (corner avoidance + room preferences)
    doors = adjust_door_positions(doors, shifted_rooms)
    
    # ── v3.0: ACCESSIBILITY ENGINE ────────────────────────────
    try:
        from services.accessibility_engine import ensure_full_accessibility
        entry_dir = "N"
        if building_program:
            entry_dir = getattr(building_program, 'entry_direction', 'N') or 'N'
        doors, accessibility_report = ensure_full_accessibility(
            shifted_rooms, doors, entry_dir
        )
    except Exception:
        accessibility_report = None
    
    windows = find_window_positions(shifted_rooms, plot_bounds, building_program)
    
    # Legacy wall-breaking (still needed for door/window symbol gaps)
    broken_walls = apply_openings_to_walls(wall_segments, doors, windows)
    
    if furniture_items is None:
        furniture_items = []
    
    # ── LAYER 0.5: SITE CONTEXT (Upgrade 4) ──────────────────
    # Note: Using plan_width_ft/height_ft to eliminate background whitespace
    draw_site_context(shifted_rooms, plan_width_ft, plan_height_ft, SCALE, offset_x, offset_y, dwg, building_program)
    
    # ── LAYER 1: ROOM POLYGONS (Professional Blueprint Standard) ────
    render_room_polygons(shifted_rooms, SCALE, offset_x, offset_y, dwg)
    
    # ── GENERATE CLIP PATH FOR FIXTURES & FURNITURE ──────────
    rooms_clip = dwg.clipPath(id="rooms_clip")
    for r in shifted_rooms:
        rx, ry = offset_x + r['x'] * SCALE, offset_y + r['y'] * SCALE
        rw, rh = r['width'] * SCALE, r['height'] * SCALE
        rooms_clip.add(dwg.rect(insert=(rx, ry), size=(rw, rh)))
    dwg.defs.add(rooms_clip)

    # Encapsulate furniture into a clipped group
    furniture_group = dwg.g(clip_path="url(#rooms_clip)")

    # ── LAYER 3: FIXTURES & FURNITURE (Drawn before walls) ───
    # PROFESSIONAL STANDARD: Skip interior markers and furniture on ROOF plan
    if not is_roof:
        render_bathroom_fixtures(shifted_rooms, doors, SCALE, offset_x, offset_y, dwg, parent_group=furniture_group)
        render_kitchen_counter(shifted_rooms, doors, SCALE, offset_x, offset_y, dwg, parent_group=furniture_group)
        if furniture_items:
            render_furniture_symbols(furniture_items, SCALE, offset_x, offset_y, dwg, parent_group=furniture_group)
    
    dwg.add(furniture_group)

    # ── LAYER 4: WALL BOUNDARY POLYGON (Professional Black Ink) ─────
    render_wall_boundary_polygon(
        wall_boundary, SCALE, offset_x, offset_y, dwg,
        wall_color=INK_COLOR, use_hatching=True,
    )
    
    # ── LAYER 4.1: DOORS ─────────────────────────────────────
    render_doors(doors, SCALE, offset_x, offset_y, dwg)
    
    # ── LAYER 4.2: WINDOWS ───────────────────────────────────
    render_windows(windows, SCALE, offset_x, offset_y, dwg)
    
    # ── LAYER 4.3: ARCHITECTURAL ELEMENTS ────────────────────
    render_staircase_symbol(shifted_rooms, SCALE, offset_x, offset_y, dwg)
    render_lift_symbol(shifted_rooms, SCALE, offset_x, offset_y, dwg)
    render_entry_marker(shifted_rooms, SCALE, offset_x, offset_y, dwg)
    
    # ── LAYER 5: ROOM LABELS (v6.0 - Architectural Centered Metric) ─────
    render_room_labels(
        shifted_rooms, SCALE, offset_x, offset_y, dwg, 
        original_unit_system=original_unit_system, is_roof=is_roof
    )
    
    # ── LAYER 6: DIMENSION LINES ─────────────────────────────
    # Dimension lines stay outside the plot, so we use offset_x/offset_y as the anchor
    render_dimension_lines(dwg, shifted_rooms, plan_width_ft, plan_height_ft, SCALE, offset_x, offset_y, original_unit_system=original_unit_system)
    
    # ── LAYER 7: COLUMNS (Solid Black CAD Style) ──────────────
    if shifted_columns:
        render_structural_columns(shifted_columns, SCALE, offset_x, offset_y, dwg)

    # ── LAYER 8: TITLE BLOCK & LEGEND (CAD Style) ────────────
    # Position title block relative to plan bottom
    title_y_start = (plan_height_ft * SCALE) + offset_y + PADDING_PX / 2
    render_title_block(dwg, vb_w, vb_h, 40, plan_width_ft, plan_height_ft, floor_number, vastu_score, building_program=building_program, is_roof=is_roof, y_offset=title_y_start)
    
    return dwg.tostring()


def render_structural_columns(columns, scale, offset_x, offset_y, dwg):



    """Renders structural columns as solid black rectangles (CAD standard)."""
    for col in columns:
        cx = offset_x + col['x'] * scale
        cy = offset_y + col['y'] * scale
        cw = col.get('width', 0.75) * scale
        ch = col.get('height', 1.0) * scale
        
        dwg.add(dwg.rect(
            insert=(cx, cy), size=(cw, ch),
            fill='#64748B', stroke='#000000', stroke_width=0.7, rx=1
        ))


def _format_dimension(value_ft: float, original_unit_system: Optional[dict] = None) -> str:
    """Formats a measurement in feet to the user's original unit system (Metric mm or Imperial ft-in)."""
    is_metric = original_unit_system and original_unit_system.get('system') == 'metric'
    
    if is_metric:
        # Convert ft to mm (1 ft = 304.8 mm)
        val_mm = round(value_ft * 304.8)
        return f"{val_mm:.0f}"
    else:
        # Imperial: ft and inches
        total_inches = round(value_ft * 12)
        ft = total_inches // 12
        inches = total_inches % 12
        return f"{int(ft)}'{int(inches):02d}\""


def render_dimension_lines(dwg, placed_rooms, plot_width, plot_height, scale, offset_x, offset_y, original_unit_system=None):



    """
    Renders AutoCAD-standard dimension lines outside the plan boundary.
    Draws overall dimensions (40px) and room-by-room facade dimensions (20px).
    """
    line_style = {"stroke": "#000000", "stroke_width": 0.5}
    text_style = {"font_size": "9px", "font_family": "Arial, sans-serif", "fill": "#000000", "text_anchor": "middle"}
    tick_style = {"stroke": "#000000", "stroke_width": 0.7}

    def draw_tick(cx, cy):
        # 45° diagonal tick marks (4px long approx)
        dwg.add(dwg.line(start=(cx - 3, cy + 3), end=(cx + 3, cy - 3), **tick_style))

    # 1. OVERALL DIMENSIONS (Top: Plot Width)
    dim_y = offset_y - 40
    # Line
    dwg.add(dwg.line(start=(offset_x, dim_y), end=(offset_x + plot_width * scale, dim_y), **line_style))
    # Outer Extension lines
    dwg.add(dwg.line(start=(offset_x, offset_y - 3), end=(offset_x, dim_y - 5), **line_style))
    dwg.add(dwg.line(start=(offset_x + plot_width * scale, offset_y - 3), end=(offset_x + plot_width * scale, dim_y - 5), **line_style))
    # Ticks
    draw_tick(offset_x, dim_y)
    draw_tick(offset_x + plot_width * scale, dim_y)
    # Text
    label = _format_dimension(plot_width, original_unit_system)
    dwg.add(dwg.text(label, insert=(offset_x + (plot_width * scale) / 2, dim_y - 4), **text_style))

    # 2. OVERALL DIMENSIONS (Right: Plot Depth)
    dim_x = offset_x + plot_width * scale + 40
    dwg.add(dwg.line(start=(dim_x, offset_y), end=(dim_x, offset_y + plot_height * scale), **line_style))
    # Extension lines
    dwg.add(dwg.line(start=(offset_x + plot_width * scale + 3, offset_y), end=(dim_x + 5, offset_y), **line_style))
    dwg.add(dwg.line(start=(offset_x + plot_width * scale + 3, offset_y + plot_height * scale), end=(dim_x + 5, offset_y + plot_height * scale), **line_style))
    # Ticks
    draw_tick(dim_x, offset_y)
    draw_tick(dim_x, offset_y + plot_height * scale)
    # Text (Rotated)
    label = _format_dimension(plot_height, original_unit_system)
    text_y = offset_y + (plot_height * scale) / 2
    dwg.add(dwg.text(label, insert=(dim_x + 12, text_y), transform=f"rotate(90, {dim_x + 12}, {text_y})", **text_style))

    # 3. ROOM DIMENSIONS (Top Facade y=0)
    top_rooms = sorted([r for r in placed_rooms if abs(r['y']) < 0.1], key=lambda r: r['x'])
    cur_x = offset_x
    dim_y_room = offset_y - 20
    for r in top_rooms:
        rw = r['width'] * scale
        # Line segment
        dwg.add(dwg.line(start=(cur_x, dim_y_room), end=(cur_x + rw, dim_y_room), **line_style))
        # Extension lines
        dwg.add(dwg.line(start=(cur_x, offset_y - 3), end=(cur_x, dim_y_room - 5), **line_style))
        dwg.add(dwg.line(start=(cur_x + rw, offset_y - 3), end=(cur_x + rw, dim_y_room - 5), **line_style))
        # Ticks
        draw_tick(cur_x, dim_y_room)
        draw_tick(cur_x + rw, dim_y_room)
        # Text
        label = _format_dimension(r['width'], original_unit_system)
        dwg.add(dwg.text(label, insert=(cur_x + rw/2, dim_y_room - 4), **text_style))
        cur_x += rw

    # 4. ROOM DIMENSIONS (Left Facade x=0)
    left_rooms = sorted([r for r in placed_rooms if abs(r['x']) < 0.1], key=lambda r: r['y'])
    cur_y = offset_y
    dim_x_room = offset_x - 20
    for r in left_rooms:
        rh = r['height'] * scale
        # Line segment
        dwg.add(dwg.line(start=(dim_x_room, cur_y), end=(dim_x_room, cur_y + rh), **line_style))
        # Extension lines
        dwg.add(dwg.line(start=(offset_x - 3, cur_y), end=(dim_x_room - 5, cur_y), **line_style))
        dwg.add(dwg.line(start=(offset_x - 3, cur_y + rh), end=(dim_x_room - 5, cur_y + rh), **line_style))
        # Ticks
        draw_tick(dim_x_room, cur_y)
        draw_tick(dim_x_room, cur_y + rh)
        # Text
        label = _format_dimension(r['height'], original_unit_system)
        dwg.add(dwg.text(label, insert=(dim_x_room - 12, cur_y + rh/2), transform=f"rotate(-90, {dim_x_room - 12}, {cur_y + rh/2})", **text_style))
        cur_y += rh


def render_room_labels_architectural(placed_rooms, scale, offset_x, offset_y, dwg, original_unit_system=None):



    """
    Renders room labels in a professional CAD style (Line 1: Bold Name, Line 2: Dims).
    Includes inter-label collision detection to prevent clutter.
    """
    placed_boxes = [] # List of (x1, y1, x2, y2)
    
    def _is_colliding(box, boxes):
        for b in boxes:
            # Check overlap with 2px buffer
            if not (box[2] < b[0]-2 or box[0] > b[2]+2 or box[3] < b[1]-2 or box[1] > b[3]+2):
                return True
        return False

    # Sort rooms by area: larger rooms get their labels placed first (more space)
    sorted_rooms = sorted(placed_rooms, key=lambda r: r['width'] * r['height'], reverse=True)

    # Skip labels on Roof if not utility
    is_roof = False
    if dwg.filename and "ROOF" in dwg.filename: # Heuristic or passed state
        is_roof = True

    for r in sorted_rooms:
        rtype = r['type'].lower()
        
        # Professional standard: No habitable room labels on Roof Plan
        if is_roof and rtype not in ['staircase', 'stair_room', 'mumty', 'water_tank', 'overhead_water_tank', 'lift_machine_room']:
            # Still render terrace label but keep it minimal
            if rtype != 'open_terrace':
                continue

        cx = offset_x + (r['x'] + r['width'] / 2) * scale
        cy = offset_y + (r['y'] + r['height'] / 2) * scale
        
        name = r.get('label', r.get('type', 'ROOM')).upper().replace('_', ' ')
        display_w = r['width'] - 0.5
        display_h = r['height'] - 0.5
        w_str = _format_dimension(display_w, original_unit_system)
        h_str = _format_dimension(display_h, original_unit_system)
        dim_str = f"{w_str} \u00d7 {h_str}"

        # Estimate label bounding box (Width approx: 7px per char for upper, 5px for dims)
        name_w = len(name) * 6.5
        dim_w = len(dim_str) * 5.0
        label_w = max(name_w, dim_w)
        label_h = 24 # 10px + 8px + 6px gap
        
        # Try finding a clear spot within the room
        found_pos = False
        # Shifts: center, then slight offsets
        shifts = [(0, 0), (0, -10), (0, 10), (-15, 0), (15, 0)]
        
        for dx, dy in shifts:
            tx, ty = cx + dx, cy + dy
            # Bounding box for the whole label block (centered)
            box = (tx - label_w/2, ty - 12, tx + label_w/2, ty + 12)
            
            # Check if this position is inside room boundaries AND not colliding with other labels
            is_inside = (r['x']*scale + margin < box[0] and (r['x']+r['width'])*scale + margin > box[2] and
                         r['y']*scale + margin < box[1] and (r['y']+r['height'])*scale + margin > box[3])
            
            if is_inside and not _is_colliding(box, placed_boxes):
                cx, cy = tx, ty
                placed_boxes.append(box)
                found_pos = True
                break
        
        if not found_pos:
            # Fallback: still place at center if no option found, but mark a collision warning in logs
            placed_boxes.append((cx - label_w/2, cy - 12, cx + label_w/2, cy + 12))

        # 1. Room Name (Line 1)
        dwg.add(dwg.text(
            name, insert=(cx, cy - 4),
            text_anchor='middle', font_size='10px',
            font_family='Arial, sans-serif', font_weight='bold',
            fill='#000000'
        ))
        
        # 2. Dimensions (Line 2)
        dwg.add(dwg.text(
            dim_str, insert=(cx, cy + 10),
            text_anchor='middle', font_size='8px',
            font_family='Arial, sans-serif', font_weight='400',
            fill='#000000', opacity=0.9
        ))


def render_title_block(dwg, canvas_width, canvas_height, margin, plot_width, plot_height, floor_number, vastu_score, building_program=None, is_roof=False, y_offset=None) -> None:
    """Renders the architectural title block/legend at the bottom of the blueprint."""
    y_start = y_offset if y_offset is not None else canvas_height - 70
    
    # Background
    dwg.add(dwg.rect(
        insert=(margin, y_start), size=(canvas_width - 2*margin, 60),
        fill='#FFFFFF', stroke='#000000', stroke_width=1
    ))
    
    # Title
    if building_program:
        title = building_program.get_floor_label(floor_number)
    else:
        floor_names = ["GROUND FLOOR PLAN", "FIRST FLOOR PLAN", "SECOND FLOOR PLAN", "THIRD FLOOR PLAN", "FOURTH FLOOR PLAN"]
        if is_roof:
            title = "ROOF PLAN"
        else:
            title = floor_names[floor_number] if floor_number < len(floor_names) else f"FLOOR {floor_number} PLAN"
    
    dwg.add(dwg.text(
        title, insert=(margin + 20, y_start + 25),
        font_size='14px', font_family='Archivo, sans-serif', font_weight='700',
        fill=INK_COLOR
    ))
    
    # Area Statement (Summary)
    area = plot_width * plot_height
    area_m2 = area * 0.092903
    dwg.add(dwg.text(
        f"TOTAL PLOT AREA: {area:.2f} SQFT / {area_m2:.2f} SQM",
        insert=(margin + 20, y_start + 45),
        font_size='9px', font_family='Inter, sans-serif', font_weight='500',
        fill=DIM_INK_COLOR
    ))
    
    # Vastu Summary (Right Side)
    if isinstance(vastu_score, dict):
        score = vastu_score.get('overall', 0)
    else:
        score = vastu_score if (isinstance(vastu_score, (int, float))) else 0
    dwg.add(dwg.text(
        f"VASTU COMPLIANCE: {score}%",
        insert=(canvas_width - margin - 20, y_start + 35),
        text_anchor='end', font_size='10px', font_family='Archivo, sans-serif',
        font_weight='600', fill=INK_COLOR
    ))


def render_entry_marker(placement_data, scale, offset_x, offset_y, dwg):



    """
    Renders an entry arrow pointing to the main entrance room.
    """
    # Find Entrance room
    entrance = next((r for r in placement_data if r['type'].lower() in ['entrance', 'main_door', 'entry', 'foyer']), None)
    
    if not entrance:
        return

    # To determine direction, we need to know which edge is exterior
    # We can infer this by checking if the room touches the plot bounds
    bounds = get_plot_bounds(placement_data)
    ex, ey = entrance['x'], entrance['y']
    ew, eh = entrance['width'], entrance['height']
    cx, cy = ex + ew/2, ey + eh/2
    
    # Check proximity to bounds (tolerance matches logic in extract_wall_segments)
    TOL = 0.5
    is_top = abs(ey - bounds['min_y']) < TOL
    is_bottom = abs((ey + eh) - bounds['max_y']) < TOL
    is_left = abs(ex - bounds['min_x']) < TOL
    is_right = abs((ex + ew) - bounds['max_x']) < TOL
    
    arrow_color = INK_COLOR 
    
    marker_x, marker_y = 0, 0
    rotation = 0
    valid_edge = False
    
    if is_bottom:
        # Arrow pointing UP at bottom edge
        marker_x = offset_x + cx * scale
        marker_y = offset_y + (ey + eh) * scale + 15
        rotation = -90
        valid_edge = True
    elif is_top:
        # Arrow pointing DOWN at top edge
        marker_x = offset_x + cx * scale
        marker_y = offset_y + ey * scale - 15
        rotation = 90
        valid_edge = True
    elif is_left:
        # Arrow pointing RIGHT at left edge
        marker_x = offset_x + ex * scale - 15
        marker_y = offset_y + cy * scale
        rotation = 0
        valid_edge = True
    elif is_right:
        # Arrow pointing LEFT at right edge
        marker_x = offset_x + (ex + ew) * scale + 15
        marker_y = offset_y + cy * scale
        rotation = 180
        valid_edge = True
    
    if not valid_edge:
        return # Not on edge, can't determine entry direction easily
        
    # Draw Arrow (Simple Triangle)
    # Tip at (0,0), Base at (-10, -5) and (-10, 5)
    # We want tip to point towards the house matches rotation 0 (Right)
    # Wait, rotation 0 means pointing Right?
    # is_left -> Pointing Right (INTO the house). Correct.
    
    dwg.add(dwg.path(
        d="M 0,0 L -12,-6 L -12,6 Z", 
        transform=f"translate({marker_x},{marker_y}) rotate({rotation})",
        fill=arrow_color,
        stroke="none"
    ))
    
    # Label "ENTRY" placement
    # Position text "behind" the arrow
    dx, dy = 0, 0
    if rotation == 0: dx = -25 # Left of arrow
    elif rotation == 180: dx = 25 # Right of arrow
    elif rotation == 90: dy = -25 # Above arrow
    elif rotation == -90: dy = 25 # Below arrow
    
    dwg.add(dwg.text(
        "ENTRY",
        insert=(marker_x + dx, marker_y + dy + 4), 
        text_anchor="middle",
        font_size="10px",
        font_family="Archivo, sans-serif",
        font_weight="700",
        fill=INK_COLOR
    ))


def render_bathroom_fixtures(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):



    """
    Renders high-fidelity CAD symbols for WC and Washbasin.
    Architectural Drafting Standard v3.0.
    """
    fixture_stroke = DIM_INK_COLOR 
    fixture_fill = ROOM_FILL
    container = parent_group if parent_group is not None else dwg
    
    for room in placed_rooms:
        if 'bathroom' not in room['type'].lower():
            continue
            
        x, y = offset_x + room['x'] * scale, offset_y + room['y'] * scale
        w, h = room['width'] * scale, room['height'] * scale
        
        # --- 1. DETAILED WC SYMBOL (Toilet) ---
        # Dimensions: approx 1.6ft x 2.4ft
        wc_w, wc_h = 1.6 * scale, 2.4 * scale
        wx, wy = x + 6, y + 6 # Offset from wall
        
        # Tank
        container.add(dwg.rect(insert=(wx, wy), size=(wc_w, wc_h * 0.25), 
                               fill=fixture_fill, stroke=fixture_stroke, stroke_width=1, rx=2))
        # Bowl/Seat
        bowl_y = wy + wc_h * 0.25
        p = dwg.path(fill=fixture_fill, stroke=fixture_stroke, stroke_width=1)
        p.push(f"M {wx + wc_w*0.1},{bowl_y}")
        p.push(f"C {wx + wc_w*0.05},{bowl_y + wc_h*0.5} {wx + wc_w*0.2},{bowl_y + wc_h*0.75} {wx + wc_w*0.5},{bowl_y + wc_h*0.75}")
        p.push(f"C {wx + wc_w*0.8},{bowl_y + wc_h*0.75} {wx + wc_w*0.95},{bowl_y + wc_h*0.5} {wx + wc_x*0.9 if 'wc_x' in locals() else wx + wc_w*0.9},{bowl_y}") # Typo fix in original logic during rewrite
        # Re-writing the path carefully:
        container.add(dwg.path(
            d=f"M {wx + wc_w*0.1},{bowl_y} "
              f"Q {wx + wc_w*0.05},{bowl_y + wc_h*0.7} {wx + wc_w*0.5},{bowl_y + wc_h*0.7} "
              f"Q {wx + wc_w*0.95},{bowl_y + wc_h*0.7} {wx + wc_w*0.9},{bowl_y} Z",
            fill=fixture_fill, stroke=fixture_stroke, stroke_width=1
        ))
        # Inner bowl line
        container.add(dwg.ellipse(center=(wx + wc_w/2, bowl_y + wc_h*0.3), r=(wc_w*0.3, wc_h*0.2), 
                                  fill="none", stroke=fixture_stroke, stroke_width=0.5, opacity=0.5))
        
        # --- 2. DETAILED WASHBASIN ---
        # Dimensions: 1.8ft x 1.5ft
        basin_w, basin_h = 1.8 * scale, 1.4 * scale
        bx = wx + wc_w + 12 # 1.2ft gap
        by = y + 6
        
        if bx + basin_w < x + w - 10:
            # Basin Counter/Outer
            container.add(dwg.rect(insert=(bx, by), size=(basin_w, basin_h), 
                                   fill=fixture_fill, stroke=fixture_stroke, stroke_width=1, rx=4))
            # Inner Bowl (Oval)
            container.add(dwg.ellipse(center=(bx + basin_w/2, by + basin_h/2 + 2), r=(basin_w*0.35, basin_h*0.3), 
                                      fill="white", stroke=fixture_stroke, stroke_width=0.75))
            # Tap Assembly
            container.add(dwg.circle(center=(bx + basin_w/2, by + 5), r=2, fill=fixture_stroke))
            container.add(dwg.line(start=(bx + basin_w/2 - 4, by + 5), end=(bx + basin_w/2 + 4, by + 5), stroke=fixture_stroke, stroke_width=1))


def render_kitchen_counter(placed_rooms, doors, scale, offset_x, offset_y, dwg, parent_group=None):



    """
    Renders a detailed L-shaped kitchen counter with high-fidelity CAD symbols.
    Architectural Drafting Standard v3.0.
    """
    counter_fill = ROOM_FILL
    counter_stroke = DIM_INK_COLOR
    counter_depth = 2.0 * scale 
    container = parent_group if parent_group is not None else dwg
    
    for room in placed_rooms:
        if 'kitchen' not in room['type'].lower():
            continue
            
        x, y = offset_x + room['x'] * scale, offset_y + room['y'] * scale
        w, h = room['width'] * scale, room['height'] * scale
        
        # --- 1. L-SHAPED COUNTERTOP ---
        # Fixed 2ft deep L-shape along top and left walls
        p = dwg.path(fill=counter_fill, stroke=counter_stroke, stroke_width=1.5)
        p.push(f"M {x},{y}")
        p.push(f"L {x+w},{y}") # Top edge
        p.push(f"L {x+w},{y+counter_depth}") # End of horizontal leg
        p.push(f"L {x+counter_depth},{y+counter_depth}") # Inner corner
        p.push(f"L {x+counter_depth},{y + h*0.75}") # End of vertical leg
        p.push(f"L {x},{y + h*0.75}") # Wall edge
        p.push("Z")
        container.add(p)
        
        # Inner line for worktop edge detail
        ip = dwg.path(fill="none", stroke=counter_stroke, stroke_width=0.5, opacity=0.4)
        ip.push(f"M {x+2},{y+counter_depth-2} L {x+w-2},{y+counter_depth-2}")
        container.add(ip)

        # --- 2. DETAILED HOB (STOVE) ---
        # Center of horizontal leg
        hob_w, hob_h = 2.2 * scale, 1.8 * scale
        hx = x + w*0.5 - hob_w/2
        hy = y + (counter_depth - hob_h)/2
        
        container.add(dwg.rect(insert=(hx, hy), size=(hob_w, hob_h), fill=INK_COLOR, rx=2))
        # 4 Burners
        for bx, by in [(hx+8, hy+6), (hx+hob_w-8, hy+6), (hx+8, hy+hob_h-6), (hx+hob_w-8, hy+hob_h-6)]:
             container.add(dwg.circle(center=(bx, by), r=4, fill=DIM_INK_COLOR, stroke=INK_COLOR, stroke_width=0.5))
             container.add(dwg.circle(center=(bx, by), r=1.5, fill=INK_COLOR)) 
        
        # --- 3. DETAILED DUAL SINK ---
        # Center of vertical leg
        sink_w, sink_h = 1.6 * scale, 2.5 * scale
        sx = x + (counter_depth - sink_w)/2
        sy = y + h*0.4 - sink_h/2
        
        # Outer Frame
        container.add(dwg.rect(insert=(sx, sy), size=(sink_w, sink_h), fill="white", stroke=counter_stroke, stroke_width=1, rx=2))
        # Two Basins
        bh = (sink_h - 6) / 2
        container.add(dwg.rect(insert=(sx+3, sy+3), size=(sink_w-6, bh), fill="none", stroke=counter_stroke, stroke_width=0.5))
        container.add(dwg.rect(insert=(sx+3, sy+3+bh+3), size=(sink_w-6, bh), fill="none", stroke=counter_stroke, stroke_width=0.5))
        # Central tap
        container.add(dwg.circle(center=(sx+sink_w/2, sy+sink_h/2), r=2, fill=counter_stroke))

def render_staircase_symbol(placement_data, scale, offset_x, offset_y, dwg):

    for room in placement_data:
        if room['type'].lower() == 'staircase':
            draw_staircase(room, scale, offset_x, offset_y, dwg)

def render_lift_symbol(placement_data, scale, offset_x, offset_y, dwg):

    for room in placement_data:
        if room['type'].lower() == 'lift':
            lx, ly = offset_x + room['x'] * scale, offset_y + room['y'] * scale
            lw, lh = room['width'] * scale, room['height'] * scale
            dwg.add(dwg.rect(insert=(lx, ly), size=(lw, lh), fill="none", stroke=INK_COLOR, stroke_width=1))
            dwg.add(dwg.line(start=(lx, ly), end=(lx+lw, ly+lh), stroke=INK_COLOR, stroke_width=0.5))
            dwg.add(dwg.line(start=(lx+lw, ly), end=(lx, ly+lh), stroke=INK_COLOR, stroke_width=0.5))

def render_entry_marker(placement_data, scale, offset_x, offset_y, dwg):

    for room in placement_data:
        if room['type'].lower() in ['entrance', 'foyer', 'entry']:
            ex, ey = offset_x + room['x'] * scale, offset_y + room['y'] * scale
            # Small arrow pointing into the entrance
            dwg.add(dwg.polygon(points=[(ex-5, ey), (ex+5, ey), (ex, ey+8)], fill=INK_COLOR))
