"""
Circulation Engine — Feature A: Adaptive Circulation Graphs
============================================================
Uses A* pathfinding to compute the minimum-cost corridor network
connecting all rooms in a BSP layout.

Key concepts:
- Rooms are nodes in a graph.
- Shared walls between adjacent rooms are free edges (no corridor needed).
- Non-adjacent rooms that need connectivity get corridor segments.
- A* finds the shortest path on a discretized grid of the plot.
- Output: a list of corridor segments that can be rendered as a distinct SVG layer.
"""
import logging

import heapq
import math
from typing import List, Dict, Any, Optional, Tuple, Set

logger = logging.getLogger(__name__)


# ── CONSTANTS ─────────────────────────────────────────────────────────────────

CORRIDOR_WIDTH_FT = 4.0          # Standard corridor width in feet
GRID_RESOLUTION_FT = 2.0         # A* grid cell size in feet
WALL_TOLERANCE = 0.5             # Tolerance for detecting shared walls (feet)

# Room types that MUST be reachable from a corridor/passage
REQUIRES_CORRIDOR_ACCESS = {
    "bedroom", "master_bedroom", "bathroom", "kitchen",
    "dining", "study", "pooja", "store", "utility"
}

# Room types that ARE corridors / circulation spaces
CIRCULATION_TYPES = {
    "passage", "corridor", "foyer", "entrance", "verandah", "balcony", "staircase"
}


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

class RoomNode:
    """A node in the circulation graph representing a single room."""

    def __init__(self, room: Dict[str, Any]):
        self.id: str = room["id"]
        self.type: str = room["type"].lower().replace(" ", "_")
        self.x: float = room["x"]
        self.y: float = room["y"]
        self.width: float = room["width"]
        self.height: float = room["height"]
        self.cx: float = room["x"] + room["width"] / 2
        self.cy: float = room["y"] + room["height"] / 2
        self.is_circulation = self.type in CIRCULATION_TYPES

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def shares_wall_with(self, other: "RoomNode") -> bool:
        """Returns True if this room shares a wall segment with another room."""
        ax1, ay1, ax2, ay2 = self.rect
        bx1, by1, bx2, by2 = other.rect

        # Vertical shared wall: right edge of A == left edge of B (or vice versa)
        if abs(ax2 - bx1) < WALL_TOLERANCE or abs(bx2 - ax1) < WALL_TOLERANCE:
            # They must overlap vertically
            overlap_y = min(ay2, by2) - max(ay1, by1)
            if overlap_y > CORRIDOR_WIDTH_FT:
                return True

        # Horizontal shared wall: bottom edge of A == top edge of B (or vice versa)
        if abs(ay2 - by1) < WALL_TOLERANCE or abs(by2 - ay1) < WALL_TOLERANCE:
            # They must overlap horizontally
            overlap_x = min(ax2, bx2) - max(ax1, bx1)
            if overlap_x > CORRIDOR_WIDTH_FT:
                return True

        return False

    def __repr__(self):
        return f"RoomNode({self.id}, cx={self.cx:.1f}, cy={self.cy:.1f})"


class CorridorSegment:
    """A rectangular corridor segment connecting two points."""

    def __init__(
        self,
        x: float, y: float,
        width: float, height: float,
        from_room: str, to_room: str,
        path_type: str = "corridor"
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.from_room = from_room
        self.to_room = to_room
        self.path_type = path_type  # "corridor" | "direct" (shared wall)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": f"corridor_{self.from_room}_to_{self.to_room}",
            "type": "corridor",
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "area": round(self.width * self.height, 2),
            "from_room": self.from_room,
            "to_room": self.to_room,
        }


# ── A* GRID PATHFINDER ────────────────────────────────────────────────────────

class AStarGrid:
    """
    Discretized grid over the plot for A* pathfinding.
    Cells inside rooms are "occupied" (high cost to traverse).
    Cells in open space are free (low cost).
    """

    def __init__(self, plot_width: float, plot_height: float, resolution: float = GRID_RESOLUTION_FT):
        self.resolution = resolution
        self.cols = max(1, int(math.ceil(plot_width / resolution)))
        self.rows = max(1, int(math.ceil(plot_height / resolution)))
        self.plot_width = plot_width
        self.plot_height = plot_height

        # Cost grid: 1.0 = free space, 10.0 = inside a room (prefer not to cut through)
        self.cost: List[List[float]] = [[1.0] * self.cols for _ in range(self.rows)]

    def world_to_grid(self, wx: float, wy: float) -> Tuple[int, int]:
        col = min(self.cols - 1, max(0, int(wx / self.resolution)))
        row = min(self.rows - 1, max(0, int(wy / self.resolution)))
        return (col, row)

    def grid_to_world(self, col: int, row: int) -> Tuple[float, float]:
        return (col * self.resolution + self.resolution / 2,
                row * self.resolution + self.resolution / 2)

    def mark_room_occupied(self, room: RoomNode, cost: float = 8.0):
        """Mark all grid cells inside a room as high-cost (prefer corridors in open space)."""
        c1, r1 = self.world_to_grid(room.x + 0.5, room.y + 0.5)
        c2, r2 = self.world_to_grid(room.x + room.width - 0.5, room.y + room.height - 0.5)
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                if 0 <= r < self.rows and 0 <= c < self.cols:
                    self.cost[r][c] = cost

    def heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Manhattan distance heuristic."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(
        self, start_world: Tuple[float, float], end_world: Tuple[float, float]
    ) -> List[Tuple[float, float]]:
        """
        A* search from start to end in world coordinates.
        Returns list of world-coordinate waypoints along the path.
        """
        start = self.world_to_grid(*start_world)
        end = self.world_to_grid(*end_world)

        if start == end:
            return [start_world, end_world]

        # Priority queue: (f_cost, g_cost, node)
        open_set: List[Tuple[float, float, Tuple[int, int]]] = []
        heapq.heappush(open_set, (0.0, 0.0, start))

        came_from: Dict[Tuple[int, int], Optional[Tuple[int, int]]] = {start: None}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}

        # 4-directional movement (no diagonals for clean corridors)
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

        while open_set:
            _, g, current = heapq.heappop(open_set)

            if current == end:
                # Reconstruct path
                path = []
                node = current
                while node is not None:
                    path.append(self.grid_to_world(*node))
                    node = came_from[node]
                path.reverse()
                return path

            for dc, dr in directions:
                neighbor = (current[0] + dc, current[1] + dr)
                nc, nr = neighbor

                if not (0 <= nc < self.cols and 0 <= nr < self.rows):
                    continue

                cell_cost = self.cost[nr][nc]
                tentative_g = g + cell_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self.heuristic(neighbor, end)
                    heapq.heappush(open_set, (f, tentative_g, neighbor))
                    came_from[neighbor] = current

        # No path found — return straight line
        return [start_world, end_world]


# ── PATH → CORRIDOR SEGMENTS ──────────────────────────────────────────────────

def _path_to_corridor_segments(
    path: List[Tuple[float, float]],
    from_id: str,
    to_id: str,
    width: float = CORRIDOR_WIDTH_FT
) -> List[CorridorSegment]:
    """
    Converts an A* waypoint path into rectangular corridor segments.
    Merges consecutive collinear segments for clean rendering.
    """
    if len(path) < 2:
        return []

    segments = []
    half_w = width / 2

    # Simplify path: merge collinear points
    simplified = [path[0]]
    for i in range(1, len(path) - 1):
        px, py = path[i - 1]
        cx, cy = path[i]
        nx, ny = path[i + 1]
        # Check if collinear (same direction)
        if not ((px == cx == nx) or (py == cy == ny)):
            simplified.append(path[i])
    simplified.append(path[-1])

    for i in range(len(simplified) - 1):
        x1, y1 = simplified[i]
        x2, y2 = simplified[i + 1]

        if abs(x1 - x2) < 0.01:
            # Vertical corridor segment
            seg_x = x1 - half_w
            seg_y = min(y1, y2)
            seg_w = width
            seg_h = abs(y2 - y1)
        else:
            # Horizontal corridor segment
            seg_x = min(x1, x2)
            seg_y = y1 - half_w
            seg_w = abs(x2 - x1)
            seg_h = width

        if seg_w > 0.1 and seg_h > 0.1:
            segments.append(CorridorSegment(
                x=seg_x, y=seg_y,
                width=seg_w, height=seg_h,
                from_room=from_id, to_room=to_id
            ))

    return segments


# ── MAIN ENGINE ───────────────────────────────────────────────────────────────

class CirculationEngine:
    """
    Computes the optimal corridor network for a given room layout.

    Algorithm:
    1. Build a graph of rooms as nodes.
    2. Detect which rooms already share walls (free edges — no corridor needed).
    3. Find the minimum spanning tree of rooms that need corridor connections.
    4. For each MST edge, run A* to find the optimal path.
    5. Convert paths to rectangular corridor segments.
    6. Compute corridor efficiency score.
    """

    def __init__(self, plot_width: float, plot_height: float):
        self.plot_width = plot_width
        self.plot_height = plot_height

    def find_optimal_corridors(
        self, placed_rooms: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Main entry point. Takes placed rooms, returns corridor data.

        Returns:
            {
                "corridors": [CorridorSegment.to_dict(), ...],
                "efficiency_score": float (0-100, higher = less wasted space),
                "total_corridor_area": float,
                "adjacency_graph": {room_id: [adjacent_room_ids]}
            }
        """
        if not placed_rooms:
            return {"corridors": [], "efficiency_score": 100.0, "total_corridor_area": 0.0}

        # 1. Build room nodes
        nodes: Dict[str, RoomNode] = {}
        for room in placed_rooms:
            node = RoomNode(room)
            nodes[node.id] = node

        # 2. Build adjacency graph (rooms sharing walls)
        adjacency: Dict[str, Set[str]] = {nid: set() for nid in nodes}
        node_list = list(nodes.values())

        for i, a in enumerate(node_list):
            for b in node_list[i + 1:]:
                if a.shares_wall_with(b):
                    adjacency[a.id].add(b.id)
                    adjacency[b.id].add(a.id)

        # 3. Find circulation "hub" rooms (passages, foyers, etc.)
        hubs = [n for n in node_list if n.is_circulation]
        private_rooms = [n for n in node_list if not n.is_circulation]

        # 4. Build A* grid
        grid = AStarGrid(self.plot_width, self.plot_height)
        for node in node_list:
            # Mark rooms as high-cost (corridors prefer open space)
            grid.mark_room_occupied(node, cost=6.0)

        # 5. Find rooms that need corridor connections
        # Strategy: connect each private room to its nearest hub (or to each other if no hub)
        all_corridor_segments: List[CorridorSegment] = []
        connected: Set[str] = set()

        if hubs:
            # Connect each private room to the nearest hub if not already adjacent
            for room in private_rooms:
                if room.type not in REQUIRES_CORRIDOR_ACCESS:
                    continue

                # Check if already adjacent to a hub
                already_connected = any(
                    hub.id in adjacency[room.id] for hub in hubs
                )
                if already_connected:
                    connected.add(room.id)
                    continue

                # Find nearest hub
                nearest_hub = min(hubs, key=lambda h: math.hypot(h.cx - room.cx, h.cy - room.cy))

                # A* path from room center to hub center
                path = grid.find_path((room.cx, room.cy), (nearest_hub.cx, nearest_hub.cy))
                segs = _path_to_corridor_segments(path, room.id, nearest_hub.id)
                all_corridor_segments.extend(segs)
                connected.add(room.id)

        else:
            # No hub — build a minimum spanning tree connecting all private rooms
            # Prim's algorithm: start from first room, greedily add nearest unconnected
            if private_rooms:
                in_tree: Set[str] = {private_rooms[0].id}
                out_tree = private_rooms[1:]

                while out_tree:
                    best_dist = float("inf")
                    best_pair = (None, None)

                    for out_node in out_tree:
                        for in_id in in_tree:
                            in_node = nodes[in_id]
                            dist = math.hypot(out_node.cx - in_node.cx, out_node.cy - in_node.cy)
                            if dist < best_dist and out_node.id not in adjacency[in_id]:
                                best_dist = dist
                                best_pair = (in_node, out_node)

                    if best_pair[0] is None:
                        # All remaining are adjacent — no corridors needed
                        break

                    from_node, to_node = best_pair
                    path = grid.find_path((from_node.cx, from_node.cy), (to_node.cx, to_node.cy))
                    segs = _path_to_corridor_segments(path, from_node.id, to_node.id)
                    all_corridor_segments.extend(segs)

                    in_tree.add(to_node.id)
                    out_tree = [n for n in out_tree if n.id not in in_tree]

        # 6. Deduplicate overlapping corridor segments
        unique_segments = _deduplicate_corridors(all_corridor_segments)

        # 7. Compute efficiency score
        total_plot_area = self.plot_width * self.plot_height
        total_corridor_area = sum(s.width * s.height for s in unique_segments)
        room_area = sum(r.get("area", r.get("width", 0) * r.get("height", 0)) for r in placed_rooms)

        # Efficiency: how close to the theoretical minimum (0 corridors = 100%)
        # Penalize for corridor area as % of total room area
        if room_area > 0:
            corridor_ratio = total_corridor_area / room_area
            efficiency_score = max(0.0, round(100.0 - (corridor_ratio * 200), 1))
        else:
            efficiency_score = 100.0

        # 8. Build adjacency graph output
        adjacency_out = {k: list(v) for k, v in adjacency.items()}

        return {
            "corridors": [s.to_dict() for s in unique_segments],
            "efficiency_score": efficiency_score,
            "total_corridor_area": round(total_corridor_area, 2),
            "adjacency_graph": adjacency_out,
        }


def _deduplicate_corridors(segments: List[CorridorSegment]) -> List[CorridorSegment]:
    """Remove corridor segments that are nearly identical (within 1ft tolerance)."""
    unique = []
    for seg in segments:
        is_dup = False
        for existing in unique:
            if (abs(seg.x - existing.x) < 1.0 and
                abs(seg.y - existing.y) < 1.0 and
                abs(seg.width - existing.width) < 1.0 and
                abs(seg.height - existing.height) < 1.0):
                is_dup = True
                break
        if not is_dup:
            unique.append(seg)
    return unique