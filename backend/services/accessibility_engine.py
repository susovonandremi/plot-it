"""
Accessibility Engine — Door Graph + BFS Verification
=====================================================
Ensures every room is reachable from the main entry through doors.

Algorithm:
1. Build a graph where nodes are rooms and edges are doors between them.
2. Identify the entry room (room closest to the plot entrance).
3. BFS from the entry room through the door graph.
4. Any room NOT reached is "isolated" — auto-fix by injecting a missing door
   on the closest shared wall to an already-reachable room.

Door sizing rules:
  - Main entry:    3.5 ft (42")
  - Bedroom:       3.0 ft (36")
  - Bathroom:      2.5 ft (30")
  - Passage/Foyer: 4.0 ft (48")
  - Kitchen:       3.0 ft (36")
  - Default:       3.0 ft (36")
"""
import logging

from collections import deque
from typing import List, Dict, Any, Set, Tuple, Optional

logger = logging.getLogger(__name__)


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

DOOR_WIDTHS = {
    "entrance": 3.5,
    "main_entry": 3.5,
    "bedroom": 3.0,
    "master_bedroom": 3.0,
    "bathroom": 2.5,
    "toilet": 2.5,
    "passage": 4.0,
    "foyer": 4.0,
    "verandah": 4.0,
    "corridor": 4.0,
    "kitchen": 3.0,
    "dining": 3.0,
    "living": 3.5,
    "pooja": 2.5,
    "study": 3.0,
    "store": 2.5,
    "utility": 2.5,
    "staircase": 3.5,
}

DEFAULT_DOOR_WIDTH = 3.0

WALL_TOL = 0.5  # Wall adjacency tolerance in feet
MIN_DOOR_MARGIN = 2.0  # Min distance from door center to wall corner


# ── SHARED WALL DETECTION ─────────────────────────────────────────────────────

def _find_shared_wall(room_a: Dict, room_b: Dict) -> Optional[Dict]:
    """Find the shared wall segment between two adjacent rooms."""
    ax1, ay1 = room_a["x"], room_a["y"]
    ax2, ay2 = ax1 + room_a["width"], ay1 + room_a["height"]
    bx1, by1 = room_b["x"], room_b["y"]
    bx2, by2 = bx1 + room_b["width"], by1 + room_b["height"]

    # Vertical shared wall (right of A == left of B or vice versa)
    if abs(ax2 - bx1) < WALL_TOL or abs(bx2 - ax1) < WALL_TOL:
        wall_x = ax2 if abs(ax2 - bx1) < WALL_TOL else bx2
        oy1 = max(ay1, by1)
        oy2 = min(ay2, by2)
        if oy2 - oy1 > MIN_DOOR_MARGIN * 2:
            return {"x": wall_x, "y1": oy1, "y2": oy2, "orientation": "vertical",
                    "length": oy2 - oy1, "mid": (oy1 + oy2) / 2}

    # Horizontal shared wall (bottom of A == top of B or vice versa)
    if abs(ay2 - by1) < WALL_TOL or abs(by2 - ay1) < WALL_TOL:
        wall_y = ay2 if abs(ay2 - by1) < WALL_TOL else by2
        ox1 = max(ax1, bx1)
        ox2 = min(ax2, bx2)
        if ox2 - ox1 > MIN_DOOR_MARGIN * 2:
            return {"y": wall_y, "x1": ox1, "x2": ox2, "orientation": "horizontal",
                    "length": ox2 - ox1, "mid": (ox1 + ox2) / 2}

    return None


def _get_door_width(room_type: str) -> float:
    """Get the standard door width for a room type."""
    return DOOR_WIDTHS.get(room_type.lower().replace(" ", "_"), DEFAULT_DOOR_WIDTH)


# ── DOOR GRAPH ────────────────────────────────────────────────────────────────

def build_door_graph(
    placed_rooms: List[Dict[str, Any]],
    doors: List[Dict[str, Any]]
) -> Dict[str, Set[str]]:
    """
    Builds an adjacency graph from existing doors.

    Each door connects two rooms. The graph maps room_id → set of reachable room_ids.
    """
    graph: Dict[str, Set[str]] = {r["id"]: set() for r in placed_rooms}

    for door in doors:
        r1 = door.get("room1_id")
        r2 = door.get("room2_id")
        if r1 and r2 and r1 in graph and r2 in graph:
            graph[r1].add(r2)
            graph[r2].add(r1)

    return graph


def _find_entry_room(placed_rooms: List[Dict[str, Any]], entry_direction: str = "N") -> str:
    """
    Finds the room closest to the plot entrance based on entry direction.
    Prefers rooms of type 'entrance', 'foyer', 'verandah', 'living', 'passage'.
    """
    entry_types = {"entrance", "foyer", "verandah", "living", "passage", "corridor"}

    # Filter for entry-type rooms
    candidates = [r for r in placed_rooms if r["type"].lower().replace(" ", "_") in entry_types]
    if not candidates:
        candidates = placed_rooms  # Fallback to all rooms

    # Score by proximity to entry edge
    def entry_score(room):
        cx = room["x"] + room["width"] / 2
        cy = room["y"] + room["height"] / 2
        d = entry_direction.upper()
        if d == "N":
            return cy  # Closest to top (y=0)
        elif d == "S":
            return -cy  # Closest to bottom
        elif d == "E":
            return -cx  # Closest to right
        elif d == "W":
            return cx  # Closest to left
        return cy

    best = min(candidates, key=entry_score)
    return best["id"]


# ── BFS ACCESSIBILITY VERIFICATION ────────────────────────────────────────────

def verify_accessibility(
    placed_rooms: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    entry_direction: str = "N"
) -> Dict[str, Any]:
    """
    Verifies that every room is reachable from the entry via doors.

    Returns:
        {
            "entry_room": str,
            "reachable": [room_id, ...],
            "isolated": [room_id, ...],
            "is_fully_accessible": bool,
            "door_count": int,
        }
    """
    graph = build_door_graph(placed_rooms, doors)
    entry_id = _find_entry_room(placed_rooms, entry_direction)

    # BFS from entry
    visited: Set[str] = set()
    queue = deque([entry_id])
    visited.add(entry_id)

    while queue:
        current = queue.popleft()
        for neighbor in graph.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    all_ids = {r["id"] for r in placed_rooms}
    isolated = all_ids - visited

    return {
        "entry_room": entry_id,
        "reachable": sorted(visited),
        "isolated": sorted(isolated),
        "is_fully_accessible": len(isolated) == 0,
        "door_count": len(doors),
    }


# ── AUTO-FIX: INJECT MISSING DOORS ────────────────────────────────────────────

def auto_fix_isolated_rooms(
    placed_rooms: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    accessibility_result: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    For each isolated room, finds the closest reachable room that shares
    a wall and injects a door between them.

    Returns updated door list with injected doors.
    """
    if accessibility_result["is_fully_accessible"]:
        return doors  # Nothing to fix

    rooms_by_id = {r["id"]: r for r in placed_rooms}
    reachable = set(accessibility_result["reachable"])
    isolated = list(accessibility_result["isolated"])
    injected_doors = list(doors)
    existing_pairs = {frozenset({d["room1_id"], d["room2_id"]}) for d in doors}

    max_iterations = len(isolated) * 2  # Safety limit
    iteration = 0

    while isolated and iteration < max_iterations:
        iteration += 1
        best_fix = None
        best_iso_id = None

        for iso_id in isolated:
            iso_room = rooms_by_id[iso_id]

            # Find the closest reachable room sharing a wall
            for reach_id in reachable:
                pair_key = frozenset({iso_id, reach_id})
                if pair_key in existing_pairs:
                    continue  # Already has a door

                reach_room = rooms_by_id[reach_id]
                shared = _find_shared_wall(iso_room, reach_room)
                if shared is None:
                    continue

                # Found a fixable pair
                if best_fix is None or shared["length"] > best_fix["length"]:
                    best_fix = shared
                    best_iso_id = iso_id
                    best_reach_id = reach_id

        if best_fix is None:
            break  # Can't fix — no shared walls with reachable rooms

        # Inject the door
        iso_type = rooms_by_id[best_iso_id]["type"].lower().replace(" ", "_")
        door_width = _get_door_width(iso_type)

        if best_fix["orientation"] == "vertical":
            door_x = best_fix["x"]
            door_y = best_fix["mid"]
        else:
            door_x = best_fix["mid"]
            door_y = best_fix["y"]

        new_door = {
            "room1_id": best_iso_id,
            "room2_id": best_reach_id,
            "room1_type": rooms_by_id[best_iso_id]["type"].lower(),
            "room2_type": rooms_by_id[best_reach_id]["type"].lower(),
            "wall_segment": {
                "x1": best_fix.get("x", best_fix.get("x1", 0)),
                "y1": best_fix.get("y1", best_fix.get("y", 0)),
                "x2": best_fix.get("x", best_fix.get("x2", 0)),
                "y2": best_fix.get("y2", best_fix.get("y", 0)),
                "orientation": best_fix["orientation"],
                "length": best_fix["length"],
            },
            "position": {"x": door_x, "y": door_y},
            "width": door_width,
            "orientation": best_fix["orientation"],
            "door_type": "injected",
            "auto_fixed": True,
        }

        injected_doors.append(new_door)
        existing_pairs.add(frozenset({best_iso_id, best_reach_id}))

        # Mark as reachable and continue
        reachable.add(best_iso_id)
        isolated.remove(best_iso_id)

    return injected_doors


# ── MAIN ENTRY DOOR (D1) ─────────────────────────────────────────────────

ENTRY_ROOM_TYPES = ['entrance', 'foyer', 'passage', 'landing', 'car_parking', 'living']


def ensure_main_entry_door(
    placed_rooms: List[Dict[str, Any]],
    plot_width: float,
    plot_height: float,
    entry_direction: str,
    doors: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Guarantees a MAIN ENTRY DOOR (D1) exists on the road-facing exterior wall.
    This door opens to the OUTSIDE, not to another room.
    Must run BEFORE the BFS accessibility check.

    Blueprint rule: D1 is always positioned on the entry (road) side,
    on the room closest to that edge, preferring entry-type rooms.
    """
    if not placed_rooms:
        return doors

    # Step 1: Find candidate rooms touching the road-facing edge
    candidates = []
    for room in placed_rooms:
        rx2 = room['x'] + room['width']
        ry2 = room['y'] + room['height']

        if entry_direction == 'S' and ry2 >= plot_height * 0.85:
            candidates.append(room)
        elif entry_direction == 'N' and room['y'] <= plot_height * 0.15:
            candidates.append(room)
        elif entry_direction == 'E' and rx2 >= plot_width * 0.85:
            candidates.append(room)
        elif entry_direction == 'W' and room['x'] <= plot_width * 0.15:
            candidates.append(room)

    if not candidates:
        candidates = list(placed_rooms)  # fallback

    # Prefer entry-type rooms
    entry_candidates = [
        r for r in candidates
        if r['type'].lower().replace(' ', '_') in ENTRY_ROOM_TYPES
    ]
    entry_room = entry_candidates[0] if entry_candidates else candidates[0]

    # Step 2: Create door on the exterior wall of the entry room
    if entry_direction == 'S':
        door_x = entry_room['x'] + entry_room['width'] / 2
        door_y = entry_room['y'] + entry_room['height']  # bottom wall
        orientation = 'horizontal'
    elif entry_direction == 'N':
        door_x = entry_room['x'] + entry_room['width'] / 2
        door_y = entry_room['y']  # top wall
        orientation = 'horizontal'
    elif entry_direction == 'E':
        door_x = entry_room['x'] + entry_room['width']  # right wall
        door_y = entry_room['y'] + entry_room['height'] / 2
        orientation = 'vertical'
    elif entry_direction == 'W':
        door_x = entry_room['x']  # left wall
        door_y = entry_room['y'] + entry_room['height'] / 2
        orientation = 'vertical'
    else:
        door_x = entry_room['x'] + entry_room['width'] / 2
        door_y = entry_room['y'] + entry_room['height']
        orientation = 'horizontal'

    main_door = {
        'room1_id': entry_room['id'],
        'room2_id': 'EXTERIOR',
        'room1_type': entry_room['type'].lower(),
        'room2_type': 'exterior',
        'position': {'x': door_x, 'y': door_y},
        'width': 3.5,  # 3.5 ft = standard main door (D1)
        'orientation': orientation,
        'door_type': 'main_entry',
        'is_main_entry': True,
    }

    # Step 3: Only add if no main entry door exists already
    existing_main = [d for d in doors if d.get('is_main_entry')]
    if not existing_main:
        doors = [main_door] + list(doors)

    return doors


# ── MAIN ENTRY POINT ────────────────────────────────────────────────────────────

def ensure_full_accessibility(
    placed_rooms: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    entry_direction: str = "N"
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Full accessibility pipeline:
    0. Ensure main entry door (D1) exists on road-facing wall
    1. Verify current door graph
    2. Auto-fix any isolated rooms
    3. Re-verify to confirm fix
    4. Return updated doors + report

    Returns:
        (updated_doors, accessibility_report)
    """
    # Infer plot dimensions from placed rooms
    plot_width = max((r['x'] + r['width']) for r in placed_rooms) if placed_rooms else 30
    plot_height = max((r['y'] + r['height']) for r in placed_rooms) if placed_rooms else 30

    # Step 0: Guarantee main entry door
    doors = ensure_main_entry_door(
        placed_rooms, plot_width, plot_height,
        entry_direction, doors
    )

    # Initial check
    result = verify_accessibility(placed_rooms, doors, entry_direction)

    if result["is_fully_accessible"]:
        result["fixes_applied"] = 0
        return doors, result

    # Auto-fix
    original_count = len(doors)
    fixed_doors = auto_fix_isolated_rooms(placed_rooms, doors, result)

    # Re-verify
    final_result = verify_accessibility(placed_rooms, fixed_doors, entry_direction)
    final_result["fixes_applied"] = len(fixed_doors) - original_count
    final_result["injected_doors"] = [d for d in fixed_doors if d.get("auto_fixed")]

    return fixed_doors, final_result