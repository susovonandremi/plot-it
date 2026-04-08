"""
Furniture Synthesis Engine — Smart Interior Furnishing
=======================================================
Auto-places standard furniture blocks with correct clearance circles.

Each room type has a predefined furniture catalog. The engine:
1. Selects appropriate furniture for the room type and dimensions.
2. Places items avoiding door swing arcs and window clearance zones.
3. Respects minimum clearance around each piece (walkway space).
4. Outputs SVG-ready furniture items with position, size, rotation.

Furniture is rendered as simplified architectural symbols (plan view):
- Beds: rectangle with pillow area
- Sofas: rectangle with back cushion
- Tables: rectangle/circle with chair positions
- Kitchen counter: L-shape or I-shape
- Toilet: circle + tank
- Washbasin: small rectangle
"""
import logging

import math
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# ── FURNITURE CATALOG ─────────────────────────────────────────────────────────

# Each furniture piece: {type, width_ft, depth_ft, clearance_ft, symbol}
FURNITURE_CATALOG = {
    "master_bedroom": [
        {"type": "king_bed", "label": "King Bed", "w": 6.5, "d": 7.0, "clearance": 2.5, "symbol": "bed", "priority": 1},
        {"type": "wardrobe", "label": "Wardrobe", "w": 6.0, "d": 2.0, "clearance": 2.0, "symbol": "wardrobe", "priority": 2},
        {"type": "side_table", "label": "Side Table", "w": 1.5, "d": 1.5, "clearance": 0.5, "symbol": "table_small", "priority": 3},
        {"type": "side_table", "label": "Side Table", "w": 1.5, "d": 1.5, "clearance": 0.5, "symbol": "table_small", "priority": 3},
    ],
    "bedroom": [
        {"type": "queen_bed", "label": "Queen Bed", "w": 5.0, "d": 6.5, "clearance": 2.0, "symbol": "bed", "priority": 1},
        {"type": "wardrobe", "label": "Wardrobe", "w": 5.0, "d": 2.0, "clearance": 2.0, "symbol": "wardrobe", "priority": 2},
        {"type": "side_table", "label": "Side Table", "w": 1.5, "d": 1.5, "clearance": 0.5, "symbol": "table_small", "priority": 3},
    ],
    "living": [
        {"type": "sofa_3seat", "label": "3-Seat Sofa", "w": 7.0, "d": 3.0, "clearance": 2.5, "symbol": "sofa", "priority": 1},
        {"type": "coffee_table", "label": "Coffee Table", "w": 4.0, "d": 2.0, "clearance": 1.5, "symbol": "table_rect", "priority": 2},
        {"type": "tv_unit", "label": "TV Unit", "w": 5.0, "d": 1.5, "clearance": 5.0, "symbol": "tv_unit", "priority": 3},
    ],
    "dining": [
        {"type": "dining_table_6", "label": "Dining Table", "w": 5.0, "d": 3.5, "clearance": 3.0, "symbol": "table_chairs", "priority": 1},
    ],
    "kitchen": [
        {"type": "counter_l", "label": "Counter", "w": 0, "d": 2.0, "clearance": 3.0, "symbol": "counter_l", "priority": 1},
        {"type": "fridge", "label": "Fridge", "w": 2.5, "d": 2.5, "clearance": 1.0, "symbol": "appliance", "priority": 2},
    ],
    "bathroom": [
        {"type": "toilet", "label": "WC", "w": 1.5, "d": 2.5, "clearance": 1.5, "symbol": "toilet", "priority": 1},
        {"type": "washbasin", "label": "Basin", "w": 2.0, "d": 1.5, "clearance": 1.5, "symbol": "basin", "priority": 2},
        {"type": "shower", "label": "Shower", "w": 3.0, "d": 3.0, "clearance": 0.5, "symbol": "shower", "priority": 3},
    ],
    "study": [
        {"type": "desk", "label": "Study Desk", "w": 4.0, "d": 2.0, "clearance": 2.5, "symbol": "desk", "priority": 1},
        {"type": "chair", "label": "Chair", "w": 1.5, "d": 1.5, "clearance": 1.0, "symbol": "chair", "priority": 2},
        {"type": "bookshelf", "label": "Bookshelf", "w": 4.0, "d": 1.0, "clearance": 1.5, "symbol": "shelf", "priority": 3},
    ],
    "pooja": [
        {"type": "altar", "label": "Altar", "w": 3.0, "d": 1.5, "clearance": 2.0, "symbol": "altar", "priority": 1},
    ],
}


# ── PLACEMENT STRATEGIES ──────────────────────────────────────────────────────

def _get_door_zones(room: Dict, doors: List[Dict]) -> List[Dict]:
    """Returns zones around door positions that furniture must avoid."""
    zones = []
    rx, ry = room["x"], room["y"]

    for door in doors:
        if door.get("room1_id") != room["id"] and door.get("room2_id") != room["id"]:
            continue
        dp = door["position"]
        dw = door.get("width", 3.0)
        # Door swing arc = semicircle of radius = door width
        zones.append({
            "cx": dp["x"] - rx,
            "cy": dp["y"] - ry,
            "radius": dw + 0.5,  # Extra clearance
        })

    return zones


def _is_in_door_zone(fx: float, fy: float, fw: float, fd: float, zones: List[Dict]) -> bool:
    """Check if a furniture piece overlaps with any door swing zone."""
    # Center of furniture
    fcx = fx + fw / 2
    fcy = fy + fd / 2

    for zone in zones:
        dist = math.hypot(fcx - zone["cx"], fcy - zone["cy"])
        if dist < zone["radius"] + max(fw, fd) / 2:
            return True
    return False


def _place_against_wall(
    room_w: float, room_h: float,
    item_w: float, item_d: float,
    wall: str, offset: float = 0.3
) -> Tuple[float, float, int]:
    """
    Place a furniture piece against a wall.
    Returns (x, y, rotation_degrees) in room-local coordinates.
    """
    if wall == "top":
        return ((room_w - item_w) / 2, offset, 0)
    elif wall == "bottom":
        return ((room_w - item_w) / 2, room_h - item_d - offset, 0)
    elif wall == "left":
        return (offset, (room_h - item_w) / 2, 90)
    elif wall == "right":
        return (room_w - item_d - offset, (room_h - item_w) / 2, 90)
    return (offset, offset, 0)


def _find_best_wall(room_w: float, room_h: float, door_zones: List[Dict]) -> str:
    """Find the wall with the least door interference."""
    walls = {
        "top": (room_w / 2, 1),
        "bottom": (room_w / 2, room_h - 1),
        "left": (1, room_h / 2),
        "right": (room_w - 1, room_h / 2),
    }

    best_wall = "bottom"
    best_dist = 0

    for wall_name, (wx, wy) in walls.items():
        min_door_dist = float("inf")
        for zone in door_zones:
            d = math.hypot(wx - zone["cx"], wy - zone["cy"])
            min_door_dist = min(min_door_dist, d)

        if min_door_dist > best_dist:
            best_dist = min_door_dist
            best_wall = wall_name

    return best_wall


# ── MAIN PLACEMENT ENGINE ─────────────────────────────────────────────────────

def place_furniture(
    placed_rooms: List[Dict[str, Any]],
    doors: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Places furniture in all rooms.
    """
    all_furniture = []

    for room in placed_rooms:
        room_type = room["type"].lower().replace(" ", "_")
        room_w = room["width"]
        room_h = room["height"]
        
        # Get furniture catalog for this room type
        catalog = FURNITURE_CATALOG.get(room_type, [])
        if not catalog:
            continue
        
        # Get door avoidance zones
        door_zones = _get_door_zones(room, doors)
        
        # Track occupied rectangles within the room
        occupied: List[Tuple[float, float, float, float]] = []
        
        for item in sorted(catalog, key=lambda x: x["priority"]):
            item_w = item["w"]
            item_d = item["d"]
            
            # Kitchen counter: auto-size to room width
            if item["symbol"] == "counter_l":
                item_w = min(room_w * 0.6, 8.0) # Cap at 8ft
                item_d = 2.0
            
            # 1. Define placement trials
            trials = []
            
            # A. Wall trials (preferred)
            # Sort walls by distance to doors (furthest first)
            walls = ["top", "bottom", "left", "right"]
            # Shuffle slightly or sort by door clearance?
            # Let's simple try best_wall first, then others
            best = _find_best_wall(room_w, room_h, door_zones)
            if best in walls:
                walls.remove(best)
                walls.insert(0, best)
            
            for wall in walls:
                trials.append(("wall", wall))
            
            # B. Center/Floating trial (fallback for tables/islands)
            if item["symbol"] in ["table_rect", "table_chairs", "table_small", "island"]:
                trials.append(("center", None))
            
            # 2. Try each placement strategy
            placed = False
            
            for strategy, param in trials:
                if placed: break
                
                # Determine candidate position/rotation
                if strategy == "wall":
                    fx, fy, rot = _place_against_wall(room_w, room_h, item_w, item_d, param)
                else: # center
                    fx = (room_w - item_w) / 2
                    fy = (room_h - item_d) / 2
                    rot = 0
                
                # Try original rotation AND rotated 90 if it fits better
                # Actually _place_against_wall handles rotation for side walls.
                # But we might want to flip item relative to wall?
                
                # Check bounds
                actual_w = item_d if rot == 90 else item_w
                actual_d = item_w if rot == 90 else item_d
                
                if fx < 0 or fy < 0 or fx + actual_w > room_w or fy + actual_d > room_h:
                    continue
                
                # Check door zones
                if _is_in_door_zone(fx, fy, actual_w, actual_d, door_zones):
                    continue
                
                # Check existing furniture overlap
                is_overlapping = False
                # Add clearance buffer
                buff = item.get("clearance", 0.5)
                
                for ox, oy, ow, oh in occupied:
                    # AABB collision with buffer
                    if (fx < ox + ow + buff and fx + actual_w + buff > ox and
                        fy < oy + oh + buff and fy + actual_d + buff > oy):
                        is_overlapping = True
                        break
                
                if not is_overlapping:
                    # Success!
                    abs_x = room["x"] + fx
                    abs_y = room["y"] + fy
                    
                    occupied.append((fx, fy, actual_w, actual_d))
                    all_furniture.append({
                        "room_id": room["id"],
                        "type": item["type"],
                        "label": item["label"],
                        "x": round(abs_x, 2),
                        "y": round(abs_y, 2),
                        "width": round(actual_w, 2),
                        "height": round(actual_d, 2),
                        "rotation": rot,
                        "symbol": item["symbol"],
                    })
                    placed = True
            
            # If still not placed, maybe try shifting along the wall?
            # (Omitted for now to avoid complexity explosion, simple multi-wall trial is big improvement)

    return all_furniture