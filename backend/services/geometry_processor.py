# backend/services/geometry_processor.py
from typing import List, Dict, Any, Optional, Tuple, Set
from shapely.geometry import box as shapely_box, Polygon
from models.geometry import (
    Orientation, WallType, Vec2, BBox, WallSegment, DoorPlacement, WindowPlacement, Room,
    normalize_room_type
)
from services.building_program import BuildingProgram
from services.constants import OVERLAP_TOL

TOLERANCE = OVERLAP_TOL  # Imported from constants.py

def get_plot_bounds(placed_rooms: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute the bounding box of the entire plot from rooms."""
    if not placed_rooms:
        return {'min_x': 0.0, 'min_y': 0.0, 'max_x': 0.0, 'max_y': 0.0}
    
    min_x = min(float(r['x']) for r in placed_rooms)
    min_y = min(float(r['y']) for r in placed_rooms)
    max_x = max(float(r['x'] + r['width']) for r in placed_rooms)
    max_y = max(float(r['y'] + r['height']) for r in placed_rooms)
    
    return {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

def merge_collinear_walls(walls: List[Dict[str, Any]], axis: str) -> List[Dict[str, Any]]:
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

def extract_wall_segments(placed_rooms: List[Dict[str, Any]], plot_bounds: Optional[Dict[str, float]] = None, shape_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Converts room rectangles into deduplicated wall segments.
    """
    if plot_bounds is None:
        plot_bounds = get_plot_bounds(placed_rooms)
    
    horizontal_walls = []
    vertical_walls = []
    
    for room in placed_rooms:
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        rid = room.get('id', 'unknown')
        
        # Top wall
        horizontal_walls.append({
            'x1': x, 'y1': y, 'x2': x + w, 'y2': y,
            'room_ids': [rid]
        })
        # Bottom wall
        horizontal_walls.append({
            'x1': x, 'y1': y + h, 'x2': x + w, 'y2': y + h,
            'room_ids': [rid]
        })
        # Left wall
        vertical_walls.append({
            'x1': x, 'y1': y, 'x2': x, 'y2': y + h,
            'room_ids': [rid]
        })
        # Right wall
        vertical_walls.append({
            'x1': x + w, 'y1': y, 'x2': x + w, 'y2': y + h,
            'room_ids': [rid]
        })
    
    horizontal_walls = merge_collinear_walls(horizontal_walls, axis='horizontal')
    vertical_walls = merge_collinear_walls(vertical_walls, axis='vertical')
    
    min_x = plot_bounds['min_x']
    min_y = plot_bounds['min_y']
    max_x = plot_bounds['max_x']
    max_y = plot_bounds['max_y']
    
    def is_ext_horizontal(y, x_min, x_max):
        if not shape_config or shape_config.get('type') == 'rectangle':
            return abs(y - min_y) < TOLERANCE or abs(y - max_y) < TOLERANCE
        
        if shape_config.get('type') in ['L_shape', 'l_shape']:
            cw = shape_config.get('cutout_width', 0)
            ch = shape_config.get('cutout_height', 0)
            if abs(y - max_y) < TOLERANCE: return True
            if abs(y - min_y) < TOLERANCE and x_max <= (max_x - cw) + TOLERANCE: return True
            if abs(y - (min_y + ch)) < TOLERANCE and x_min >= (max_x - cw) - TOLERANCE: return True
            
        return False

    def is_ext_vertical(x, y_min, y_max):
        if not shape_config or shape_config.get('type') == 'rectangle':
            return abs(x - min_x) < TOLERANCE or abs(x - max_x) < TOLERANCE
            
        if shape_config.get('type') in ['L_shape', 'l_shape']:
            cw = shape_config.get('cutout_width', 0)
            ch = shape_config.get('cutout_height', 0)
            if abs(x - min_x) < TOLERANCE: return True
            if abs(x - max_x) < TOLERANCE and y_min >= (min_y + ch) - TOLERANCE: return True
            if abs(x - (max_x - cw)) < TOLERANCE and y_max <= (min_y + ch) + TOLERANCE: return True
            
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

def find_shared_wall(room1: Dict[str, Any], room2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Finds the shared wall segment between two adjacent rooms.
    """
    r1x, r1y = room1['x'], room1['y']
    r1w, r1h = room1['width'], room1['height']
    r2x, r2y = room2['x'], room2['y']
    r2w, r2h = room2['width'], room2['height']
    
    if abs((r1x + r1w) - r2x) < TOLERANCE:
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

def find_door_positions(placed_rooms: List[Dict[str, Any]], building_program: Optional[BuildingProgram] = None) -> List[Dict[str, Any]]:
    """
    Places doors on shared walls between adjacent rooms.
    Uses canonical room type normalization to resolve forbidden pairs.
    """
    doors = []
    seen_pairs: Set[frozenset] = set()
    has_circulation_access: Set[str] = set()
    
    CIRCULATION_HUBS = {'passage', 'hallway', 'foyer', 'living', 'dining', 'corridor'}
    
    # Sort rooms for deterministic behavior
    rooms = sorted(placed_rooms, key=lambda r: r['id'])
    
    for i, room1 in enumerate(rooms):
        r1_id = room1['id']
        r1_type = normalize_room_type(room1['type'])
        is_r1_hub = r1_type in CIRCULATION_HUBS

        if not is_r1_hub and r1_id in has_circulation_access:
            if r1_type != 'kitchen':
                continue

        for room2 in rooms[i + 1:]:
            r2_id = room2['id']
            r2_type = normalize_room_type(room2['type'])
            is_r2_hub = r2_type in CIRCULATION_HUBS
            
            pair_key = frozenset({r1_id, r2_id})
            if pair_key in seen_pairs:
                continue
            
            if not is_r1_hub and is_r2_hub and r1_id in has_circulation_access and r1_type != 'kitchen':
                continue
            if is_r1_hub and not is_r2_hub and r2_id in has_circulation_access and r2_type != 'kitchen':
                continue

            # Check budgets and forbidden pairs
            if building_program:
                door_config = building_program.should_place_door(r1_type, r2_type)
                if door_config is None:
                    continue
                door_width = door_config['width']
                door_type = door_config['type']
            else:
                type_pair = frozenset({r1_type, r2_type})
                from services.building_program import NO_DOOR_PAIRS
                if type_pair in NO_DOOR_PAIRS:
                    continue
                door_width = 3.0
                door_type = 'internal'
            
            shared = find_shared_wall(room1, room2)
            if shared is None:
                continue
            
            if shared['length'] < door_width + 1.2:
                continue
            
            seen_pairs.add(pair_key)
            if not is_r1_hub and is_r2_hub:
                has_circulation_access.add(r1_id)
            if is_r1_hub and not is_r2_hub:
                has_circulation_access.add(r2_id)

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
            
    # ── Auto-place Main Entrance Door ──────────────────────────────
    # Locate the main entry room (foyer, else living, else entrance)
    entry_room = None
    for rtype in ('foyer', 'living', 'entrance'):
        candidates = [r for r in rooms if r.get('type', '').lower().replace(' ', '_').replace('_room', '') == rtype]
        if candidates:
            entry_room = candidates[0]
            break
    if not entry_room and rooms:
        entry_room = rooms[0]
        
    if entry_room:
        er_id = entry_room['id']
        er_type = entry_room.get('type', '').lower().replace(' ', '_').replace('_room', '')
        
        # Decide which wall is the exterior entry wall based on entry_direction
        entry_direction = 'S'
        if building_program and hasattr(building_program, 'entry_direction'):
            entry_direction = building_program.entry_direction
            
        rx, ry = entry_room['x'], entry_room['y']
        rw, rh = entry_room['width'], entry_room['height']
        
        main_door_width = 3.5
        main_door_x = rx + rw / 2
        main_door_y = ry + rh / 2
        main_door_orientation = 'horizontal'
        
        if entry_direction == 'S':
            main_door_x = rx + rw / 2
            main_door_y = ry + rh
            main_door_orientation = 'horizontal'
        elif entry_direction == 'N':
            main_door_x = rx + rw / 2
            main_door_y = ry
            main_door_orientation = 'horizontal'
        elif entry_direction == 'W':
            main_door_x = rx
            main_door_y = ry + rh / 2
            main_door_orientation = 'vertical'
        elif entry_direction == 'E':
            main_door_x = rx + rw
            main_door_y = ry + rh / 2
            main_door_orientation = 'vertical'
            
        # Append main entrance door (room2_id is 'outside')
        doors.append({
            'room1_id': er_id,
            'room2_id': 'outside',
            'room1_type': er_type,
            'room2_type': 'outside',
            'wall_segment': {
                'x1': rx if main_door_orientation == 'horizontal' else main_door_x,
                'y1': ry if main_door_orientation == 'vertical' else main_door_y,
                'x2': rx + rw if main_door_orientation == 'horizontal' else main_door_x,
                'y2': ry + rh if main_door_orientation == 'vertical' else main_door_y,
                'orientation': main_door_orientation,
                'length': rw if main_door_orientation == 'horizontal' else rh
            },
            'position': {'x': main_door_x, 'y': main_door_y},
            'width': main_door_width,
            'orientation': main_door_orientation,
            'door_type': 'main',
        })
    
    return doors

def find_window_positions(placed_rooms: List[Dict[str, Any]], plot_bounds: Dict[str, float], building_program: Optional[BuildingProgram] = None) -> List[Dict[str, Any]]:
    """
    Places windows on exterior walls of eligible rooms.
    """
    windows = []
    WINDOW_ELIGIBLE = {'bedroom', 'master_bedroom', 'living', 'dining', 'kitchen', 'study'}
    
    for room in placed_rooms:
        rtype = normalize_room_type(room['type'])
        
        if building_program:
            budget = building_program.get_window_budget(rtype)
            max_windows = budget['count']
            win_width = budget['width']
            win_type = budget['type']
            if max_windows == 0:
                continue
        else:
            if rtype not in WINDOW_ELIGIBLE:
                continue
            max_windows = 99
            win_width = 4.0
            win_type = 'standard'
        
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        
        exterior_walls = []
        
        if abs(y - plot_bounds['min_y']) < TOLERANCE and w > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y, 'x2': x + w, 'y2': y,
                'orientation': 'horizontal', 'side': 'top'
            })
        
        if abs((y + h) - plot_bounds['max_y']) < TOLERANCE and w > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y + h, 'x2': x + w, 'y2': y + h,
                'orientation': 'horizontal', 'side': 'bottom'
            })
        
        if abs(x - plot_bounds['min_x']) < TOLERANCE and h > win_width + 1.0:
            exterior_walls.append({
                'x1': x, 'y1': y, 'x2': x, 'y2': y + h,
                'orientation': 'vertical', 'side': 'left'
            })
        
        if abs((x + w) - plot_bounds['max_x']) < TOLERANCE and h > win_width + 1.0:
            exterior_walls.append({
                'x1': x + w, 'y1': y, 'x2': x + w, 'y2': y + h,
                'orientation': 'vertical', 'side': 'right'
            })
        
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

def split_wall_at_opening(wall: Dict[str, Any], opening_pos: float, opening_width: float, axis: str) -> List[Dict[str, Any]]:
    """
    Splits a wall segment into two at an opening (door/window).
    """
    half = opening_width / 2
    result = []
    
    if axis == 'horizontal':
        gap_start = opening_pos - half
        gap_end = opening_pos + half
        
        if gap_start > wall['x1'] + TOLERANCE:
            left = dict(wall)
            left['x2'] = gap_start
            result.append(left)
        
        if gap_end < wall['x2'] - TOLERANCE:
            right = dict(wall)
            right['x1'] = gap_end
            result.append(right)
    else:
        gap_start = opening_pos - half
        gap_end = opening_pos + half
        
        if gap_start > wall['y1'] + TOLERANCE:
            top = dict(wall)
            top['y2'] = gap_start
            result.append(top)
        
        if gap_end < wall['y2'] - TOLERANCE:
            bottom = dict(wall)
            bottom['y1'] = gap_end
            result.append(bottom)
            
    return result

def apply_openings_to_walls(wall_segments: Dict[str, List[Dict[str, Any]]], doors: List[Dict[str, Any]], windows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Breaks wall segments wherever doors or windows exist.
    """
    h_walls = list(wall_segments['horizontal'])
    v_walls = list(wall_segments['vertical'])
    
    for door in doors:
        dx = door['position']['x']
        dy = door['position']['y']
        dw = door['width']
        
        if door['orientation'] == 'vertical':
            new_v = []
            for wall in v_walls:
                if (abs(wall['x1'] - dx) < TOLERANCE and
                    wall['y1'] <= dy + TOLERANCE and
                    wall['y2'] >= dy - TOLERANCE):
                    new_v.extend(split_wall_at_opening(wall, dy, dw, 'vertical'))
                else:
                    new_v.append(wall)
            v_walls = new_v
        else:
            new_h = []
            for wall in h_walls:
                if (abs(wall['y1'] - dy) < TOLERANCE and
                    wall['x1'] <= dx + TOLERANCE and
                    wall['x2'] >= dx - TOLERANCE):
                    new_h.extend(split_wall_at_opening(wall, dx, dw, 'horizontal'))
                else:
                    new_h.append(wall)
            h_walls = new_h
            
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


def _build_room_polygons(placed_rooms: List[Dict[str, Any]]) -> List[Polygon]:
    """Convert placed room dicts into a list of Shapely box polygons."""
    from shapely.geometry import box as shapely_box
    polys = []
    for room in placed_rooms:
        if room.get('is_annotation'):
            continue
        x, y = room['x'], room['y']
        w, h = room['width'], room['height']
        if w > 0 and h > 0:
            polys.append(shapely_box(x, y, x + w, y + h))
    return polys


def _build_wall_boundary(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    ext_thickness: float = 0.75,
    int_thickness: float = 0.375,
) -> Any:
    """
    Convenience wrapper: builds room Shapely polygons + plot polygon,
    calls generate_wall_boundary from structural_engine.
    """
    from shapely.geometry import box as shapely_box
    from services.structural_engine import generate_wall_boundary
    room_polys = _build_room_polygons(placed_rooms)
    plot_poly = shapely_box(0, 0, plot_width, plot_height)
    return generate_wall_boundary(room_polys, plot_poly, ext_thickness, int_thickness)


GRID_UNIT = 0.5  # feet (6 inches)

def snap_to_grid(value: float) -> float:
    """Snap a coordinate to the nearest half-foot."""
    return round(value / GRID_UNIT) * GRID_UNIT

def snap_bbox(bbox: Any) -> Any:
    """Snap a bounding box to the grid, preserving minimum dimensions."""
    from models.geometry import BBox
    return BBox(
        snap_to_grid(bbox.x),
        snap_to_grid(bbox.y),
        max(GRID_UNIT, snap_to_grid(bbox.width)),
        max(GRID_UNIT, snap_to_grid(bbox.height)),
    )
