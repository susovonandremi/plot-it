"""
Building Program Service
=========================
Decides WHAT a building needs based on architectural context.

This is the "architectural brain" that sits between NLP parsing and layout.
It takes raw room requests and enriches them with:
- Mandatory elements (entry, stairs, lift, passage)
- Smart door placement rules (budget per room pair)
- Smart window placement rules (budget per room type)
- Building type awareness (apartment vs house vs villa)

Architecture:
  NLP Parser → BuildingProgram → BSP Layout → Professional Renderer

The program generator answers: "What rooms does this building NEED?"
The door/window budgets answer: "How many openings should each room GET?"
"""
import logging
import uuid

from typing import List, Dict, Any, Optional, Tuple
import math

# ── Shapely computational geometry ────────────────────────────────────────────
from shapely.geometry import Polygon, box as shapely_box
from shapely.ops import unary_union

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# GEOMETRY MODELS  (Shapely-backed, renderer-compatible)
# ═══════════════════════════════════════════════════════════════════════

class Room:
    """
    A room defined by a rectangular Shapely Polygon (via ``shapely.geometry.box``).

    Coordinates are in **metres** (the rest of the engine uses feet; conversion
    is the caller's responsibility when mixing units — keep one system per
    FloorPlan instance).

    Parameters
    ----------
    room_type : str
        Canonical room type string (e.g. ``"bedroom"``, ``"passage"``).
    minx, miny : float
        Bottom-left corner of the room.
    maxx, maxy : float
        Top-right corner of the room.
    room_id : str, optional
        Unique identifier.  Auto-generated (UUID4 prefix) if omitted.
    floor : int, optional
        Floor number this room belongs to.
    label : str, optional
        Human-readable display label (defaults to *room_type*).
    area_hint : float, optional
        Requested area in m².  Stored for reference; overridden by the actual
        polygon area when the room is constructed.
    """

    def __init__(
        self,
        room_type: str,
        minx: float,
        miny: float,
        maxx: float,
        maxy: float,
        room_id: Optional[str] = None,
        floor: int = 0,
        label: Optional[str] = None,
        area_hint: Optional[float] = None,
        **extra_attrs: Any,
    ):
        if maxx <= minx or maxy <= miny:
            raise ValueError(
                f"Room '{room_type}': maxx/maxy must be strictly greater than "
                f"minx/miny. Got ({minx},{miny}) → ({maxx},{maxy})."
            )

        self.room_type: str = room_type.lower()
        self.polygon: Polygon = shapely_box(minx, miny, maxx, maxy)
        self.id: str = room_id or f"{self.room_type}_{uuid.uuid4().hex[:6]}"
        self.floor: int = floor
        self.label: str = label or room_type
        self.area_hint: Optional[float] = area_hint
        # Any extra keyword arguments are stored for downstream consumers
        self.extra: Dict[str, Any] = extra_attrs

    # ── Geometry helpers ──────────────────────────────────────────────

    @property
    def minx(self) -> float:
        return self.polygon.bounds[0]

    @property
    def miny(self) -> float:
        return self.polygon.bounds[1]

    @property
    def maxx(self) -> float:
        return self.polygon.bounds[2]

    @property
    def maxy(self) -> float:
        return self.polygon.bounds[3]

    @property
    def width(self) -> float:
        """Width in the X direction."""
        return self.maxx - self.minx

    @property
    def height(self) -> float:
        """Height in the Y direction."""
        return self.maxy - self.miny

    @property
    def area(self) -> float:
        """Exact polygon area (m² or ft² depending on coordinate system)."""
        return self.polygon.area

    @property
    def centroid(self) -> Tuple[float, float]:
        """(cx, cy) centroid of the room polygon."""
        c = self.polygon.centroid
        return (c.x, c.y)

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Emit a renderer-compatible dict identical in shape to the legacy
        ``placed_rooms`` dicts used throughout the SVG pipeline.

        Keys produced
        -------------
        id, type, x, y, width, height, area, floor, label, centroid
        """
        cx, cy = self.centroid
        result: Dict[str, Any] = {
            "id": self.id,
            "type": self.room_type,
            "label": self.label,
            "x": round(self.minx, 4),
            "y": round(self.miny, 4),
            "width": round(self.width, 4),
            "height": round(self.height, 4),
            "area": round(self.area, 4),
            "floor": self.floor,
            "centroid": {"x": round(cx, 4), "y": round(cy, 4)},
        }
        # Merge any stored extra attributes (do not override computed keys)
        for k, v in self.extra.items():
            result.setdefault(k, v)
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Room":
        """
        Reconstruct a ``Room`` from a legacy renderer dict.

        Accepts both ``(x, y, width, height)`` and ``(minx, miny, maxx, maxy)``
        layouts so it is backwards-compatible with the existing pipeline.
        """
        # Support legacy x/y/width/height layout
        if "x" in d and "width" in d:
            minx = float(d["x"])
            miny = float(d["y"])
            maxx = minx + float(d["width"])
            maxy = miny + float(d["height"])
        else:
            minx, miny, maxx, maxy = (
                float(d["minx"]), float(d["miny"]),
                float(d["maxx"]), float(d["maxy"]),
            )

        known_keys = {"id", "type", "x", "y", "width", "height",
                      "area", "floor", "label", "centroid",
                      "minx", "miny", "maxx", "maxy"}
        extra = {k: v for k, v in d.items() if k not in known_keys}

        return cls(
            room_type=d.get("type", "unknown"),
            minx=minx, miny=miny, maxx=maxx, maxy=maxy,
            room_id=d.get("id"),
            floor=int(d.get("floor", 0)),
            label=d.get("label"),
            area_hint=d.get("area_hint"),
            **extra,
        )

    def __repr__(self) -> str:
        return (
            f"<Room id={self.id!r} type={self.room_type!r} "
            f"bbox=({self.minx:.2f},{self.miny:.2f},{self.maxx:.2f},{self.maxy:.2f}) "
            f"area={self.area:.2f}>"
        )


class FloorPlan:
    """
    A complete floor plan: a plot polygon plus a collection of :class:`Room`
    objects that tile (or partially tile) it.

    Parameters
    ----------
    plot_width, plot_height : float
        Outer dimensions of the plot in the same unit as all ``Room`` coordinates.
    rooms : list of Room, optional
        Initial room list.  Rooms can be added later via :meth:`add_room`.
    floor : int, optional
        Floor number this plan represents.
    """

    def __init__(
        self,
        plot_width: float,
        plot_height: float,
        rooms: Optional[List[Room]] = None,
        floor: int = 0,
    ):
        self.plot_width = plot_width
        self.plot_height = plot_height
        self.floor = floor
        # The canonical plot polygon — a simple axis-aligned rectangle.
        self.plot_polygon: Polygon = shapely_box(0.0, 0.0, plot_width, plot_height)
        self._rooms: List[Room] = list(rooms or [])

    # ── Room management ───────────────────────────────────────────────

    def add_room(self, room: Room) -> None:
        """Append a room to this floor plan."""
        self._rooms.append(room)

    @property
    def rooms(self) -> List[Room]:
        """Read-only snapshot of the current room list."""
        return list(self._rooms)

    # ── Geometry helpers ──────────────────────────────────────────────

    @property
    def total_room_area(self) -> float:
        """Sum of individual room polygon areas."""
        return sum(r.area for r in self._rooms)

    @property
    def coverage_ratio(self) -> float:
        """
        Fraction of the plot polygon covered by the union of all room polygons.
        A perfectly packed plan returns 1.0; gaps appear as values < 1.0.
        """
        if not self._rooms:
            return 0.0
        union = unary_union([r.polygon for r in self._rooms])
        return union.area / self.plot_polygon.area

    def room_union(self) -> Polygon:
        """Shapely union of every room polygon on this floor."""
        if not self._rooms:
            return Polygon()  # empty geometry
        return unary_union([r.polygon for r in self._rooms])

    # ── Serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Emit a renderer-compatible dict that mirrors the legacy API response
        shape expected by the SVG pipeline.
        """
        return {
            "floor": self.floor,
            "plot_width": self.plot_width,
            "plot_height": self.plot_height,
            "plot_area": round(self.plot_polygon.area, 4),
            "coverage_ratio": round(self.coverage_ratio, 4),
            "rooms": [r.to_dict() for r in self._rooms],
        }

    @classmethod
    def from_placed_rooms(
        cls,
        placed_rooms: List[Dict[str, Any]],
        plot_width: float,
        plot_height: float,
        floor: int = 0,
    ) -> "FloorPlan":
        """
        Build a :class:`FloorPlan` from the legacy ``placed_rooms`` list that
        the existing layout engine produces.
        """
        fp = cls(plot_width=plot_width, plot_height=plot_height, floor=floor)
        for d in placed_rooms:
            try:
                fp.add_room(Room.from_dict(d))
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping malformed room dict %s: %s", d.get("id"), exc)
        return fp

    def __repr__(self) -> str:
        return (
            f"<FloorPlan floor={self.floor} "
            f"plot=({self.plot_width}×{self.plot_height}) "
            f"rooms={len(self._rooms)}>"
        )


# ═══════════════════════════════════════════════════════════════════════
# BUILDING TYPES
# ═══════════════════════════════════════════════════════════════════════

class BuildingType:
    INDEPENDENT_HOUSE = "independent_house"
    APARTMENT = "apartment"
    VILLA = "villa"
    ROW_HOUSE = "row_house"


# ═══════════════════════════════════════════════════════════════════════
# DOOR RULES — Budget per room-pair relationship
# ═══════════════════════════════════════════════════════════════════════
#
# Real buildings have 4-8 doors, not 11.
# The old system put a door on EVERY shared wall — completely wrong.
#
# Rules:
#   - Entry → passage/foyer: 1 main door (wider, 3.5ft)
#   - Bedroom → passage: 1 door per bedroom
#   - Bedroom → attached bathroom: 1 door (if en-suite)
#   - Kitchen → dining/passage: 1 door
#   - Living → passage: open arch OR 1 door
#
# NO DOORS between:
#   - bedroom ↔ bedroom
#   - bathroom ↔ bathroom
#   - kitchen ↔ bedroom
#   - bathroom ↔ dining
#   - bathroom ↔ kitchen
#   - staircase ↔ any room (staircase opens to passage only)
#   - lift ↔ any room (lift opens to passage only)

# Pairs that SHOULD get a door (ordered by priority)
DOOR_ALLOWED_PAIRS = {
    # (room_type_1, room_type_2): {'width': ft, 'type': style}
    frozenset({'entry', 'passage'}):        {'width': 3.5, 'type': 'main_door'},
    frozenset({'entry', 'living'}):         {'width': 3.5, 'type': 'main_door'},
    frozenset({'entry', 'foyer'}):          {'width': 3.5, 'type': 'main_door'},
    frozenset({'bedroom', 'passage'}):      {'width': 3.0, 'type': 'internal'},
    frozenset({'bedroom', 'hallway'}):      {'width': 3.0, 'type': 'internal'},
    frozenset({'bedroom', 'bathroom'}):     {'width': 2.5, 'type': 'internal'},
    frozenset({'master_bedroom', 'passage'}):  {'width': 3.0, 'type': 'internal'},
    frozenset({'master_bedroom', 'hallway'}):  {'width': 3.0, 'type': 'internal'},
    frozenset({'master_bedroom', 'bathroom'}): {'width': 2.5, 'type': 'internal'},
    frozenset({'kitchen', 'dining'}):       {'width': 3.0, 'type': 'internal'},
    frozenset({'kitchen', 'passage'}):      {'width': 3.0, 'type': 'internal'},
    frozenset({'kitchen', 'hallway'}):      {'width': 3.0, 'type': 'internal'},
    frozenset({'living', 'passage'}):       {'width': 4.0, 'type': 'open_arch'},
    frozenset({'living', 'hallway'}):       {'width': 4.0, 'type': 'open_arch'},
    frozenset({'living', 'dining'}):        {'width': 4.0, 'type': 'open_arch'},
    frozenset({'dining', 'passage'}):       {'width': 3.0, 'type': 'internal'},
    frozenset({'dining', 'hallway'}):       {'width': 3.0, 'type': 'internal'},
    frozenset({'study', 'passage'}):        {'width': 3.0, 'type': 'internal'},
    frozenset({'study', 'hallway'}):        {'width': 3.0, 'type': 'internal'},
    frozenset({'pooja', 'passage'}):        {'width': 2.5, 'type': 'internal'},
    frozenset({'pooja', 'hallway'}):        {'width': 2.5, 'type': 'internal'},
    frozenset({'pooja', 'living'}):         {'width': 2.5, 'type': 'internal'},
    frozenset({'bathroom', 'passage'}):     {'width': 2.5, 'type': 'internal'},
    frozenset({'bathroom', 'hallway'}):     {'width': 2.5, 'type': 'internal'},
}

# Pairs that MUST NOT get a door (ever)
NO_DOOR_PAIRS = {
    frozenset({'bedroom', 'bedroom'}),
    frozenset({'bedroom', 'kitchen'}),
    frozenset({'bedroom', 'master_bedroom'}),
    frozenset({'master_bedroom', 'master_bedroom'}),
    frozenset({'master_bedroom', 'kitchen'}),
    frozenset({'bathroom', 'bathroom'}),
    frozenset({'bathroom', 'kitchen'}),
    frozenset({'bathroom', 'dining'}),
    frozenset({'bathroom', 'living'}),
    frozenset({'staircase', 'bedroom'}),
    frozenset({'staircase', 'master_bedroom'}),
    frozenset({'staircase', 'bathroom'}),
    frozenset({'staircase', 'kitchen'}),
    frozenset({'lift', 'bedroom'}),
    frozenset({'lift', 'master_bedroom'}),
    frozenset({'lift', 'bathroom'}),
    frozenset({'lift', 'kitchen'}),
    frozenset({'living', 'kitchen'}),
    frozenset({'living', 'bedroom'}),
    frozenset({'living', 'master_bedroom'}),
    frozenset({'dining', 'bedroom'}),
    frozenset({'dining', 'master_bedroom'}),
    frozenset({'dining', 'bathroom'}),
}


# ═══════════════════════════════════════════════════════════════════════
# WINDOW RULES — Budget per room type
# ═══════════════════════════════════════════════════════════════════════
#
# Real buildings have 6-10 windows max for 2000 sqft.
# Not every exterior wall gets a window.
#
# Budget: each room type gets a fixed window count regardless of
# how many exterior walls it touches.

WINDOW_BUDGET = {
    'master_bedroom': {'count': 2, 'width': 4.0, 'type': 'standard'},
    'bedroom':        {'count': 1, 'width': 4.0, 'type': 'standard'},
    'living':         {'count': 2, 'width': 5.0, 'type': 'large'},
    'dining':         {'count': 1, 'width': 4.0, 'type': 'standard'},
    'kitchen':        {'count': 1, 'width': 3.5, 'type': 'standard'},
    'study':          {'count': 1, 'width': 4.0, 'type': 'standard'},
    'bathroom':       {'count': 1, 'width': 1.5, 'type': 'ventilator'},
    'pooja':          {'count': 0, 'width': 0,   'type': 'none'},
    'passage':        {'count': 0, 'width': 0,   'type': 'none'},
    'hallway':        {'count': 0, 'width': 0,   'type': 'none'},
    'staircase':      {'count': 0, 'width': 0,   'type': 'none'},
    'lift':           {'count': 0, 'width': 0,   'type': 'none'},
    'entry':          {'count': 0, 'width': 0,   'type': 'none'},
    'foyer':          {'count': 0, 'width': 0,   'type': 'none'},
    'verandah':       {'count': 0, 'width': 0,   'type': 'none'},
    'garage':         {'count': 1, 'width': 3.0, 'type': 'standard'},
}


# ═══════════════════════════════════════════════════════════════════════
# MANDATORY ELEMENTS — What every building type MUST have
# ═══════════════════════════════════════════════════════════════════════

MANDATORY_ELEMENTS = {
    BuildingType.INDEPENDENT_HOUSE: {
        'ground_floor': [
            {'type': 'Passage', 'count': 1, 'min_area': 40, 'max_area_pct': 0.10,
             'notes': 'Central corridor connecting rooms'},
        ],
        'upper_floor': [
            {'type': 'Staircase', 'count': 1, 'fixed_area': 50,
             'notes': 'Staircase from lower floor'},
            {'type': 'Passage', 'count': 1, 'min_area': 35, 'max_area_pct': 0.08,
             'notes': 'Corridor connecting rooms'},
        ],
    },
    BuildingType.APARTMENT: {
        'ground_floor': [
            {'type': 'Passage', 'count': 1, 'min_area': 35, 'max_area_pct': 0.08,
             'notes': 'Internal corridor'},
        ],
        'upper_floor': [
            {'type': 'Passage', 'count': 1, 'min_area': 35, 'max_area_pct': 0.08,
             'notes': 'Internal corridor'},
            {'type': 'Entrance', 'count': 1, 'min_area': 25, 'max_area_pct': 0.05,
             'notes': 'Main entry foyer'},
        ],
    },
    BuildingType.VILLA: {
        'ground_floor': [
            {'type': 'Foyer', 'count': 1, 'min_area': 50, 'max_area_pct': 0.06,
             'notes': 'Grand entrance foyer'},
            {'type': 'Passage', 'count': 1, 'min_area': 50, 'max_area_pct': 0.12,
             'notes': 'Wide corridor'},
        ],
        'upper_floor': [
            {'type': 'Staircase', 'count': 1, 'fixed_area': 60,
             'notes': 'Wide staircase'},
            {'type': 'Passage', 'count': 1, 'min_area': 40, 'max_area_pct': 0.10,
             'notes': 'Upper floor corridor'},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# ADJACENCY RULES — Which rooms must/must-not be neighbors
# ═══════════════════════════════════════════════════════════════════════

# These rooms SHOULD be adjacent (sorted by priority)
PREFERRED_ADJACENCY = [
    ('kitchen', 'dining'),          # Kitchen should open to dining
    ('bedroom', 'bathroom'),        # Attached bathroom for bedrooms
    ('living', 'dining'),           # Living-dining is a common flow
    ('entry', 'living'),            # Entry → living is the natural flow
    ('passage', 'bedroom'),         # Bedrooms open to corridor
    ('passage', 'kitchen'),         # Kitchen accessible from corridor
    ('passage', 'living'),          # Living accessible from corridor
    ('passage', 'staircase'),       # Staircase opens to corridor
]

# These rooms MUST NOT be adjacent
FORBIDDEN_ADJACENCY = [
    ('kitchen', 'bedroom'),         # Cooking fumes → sleeping = bad
    ('bathroom', 'kitchen'),        # Hygiene concerns
    ('bathroom', 'dining'),         # Nobody wants this
]


# ═══════════════════════════════════════════════════════════════════════
# BUILDING PROGRAM GENERATOR
# ═══════════════════════════════════════════════════════════════════════

class BuildingProgram:
    """
    Generates the complete architectural program for a building.
    
    Given user input (rooms, plot size, building type), this class:
    1. Injects mandatory elements (passage, stairs, etc.)
    2. Validates the room program against the plot size
    3. Provides door/window budgets for the renderer
    4. Provides adjacency constraints for the layout engine
    
    Usage:
        program = BuildingProgram(
            plot_area=2000,
            building_type="apartment",
            floor_number=3,
            floors_total=4,
            entry_direction="E",
            user_rooms=[...],
            has_lift=True
        )
        enriched_rooms = program.get_enriched_rooms()
        door_budget = program.get_door_budget()
        window_budget = program.get_window_budget()
    """
    
    def __init__(
        self,
        plot_area: float,
        building_type: str = BuildingType.INDEPENDENT_HOUSE,
        floor_number: int = 0,
        floors_total: int = 1,
        entry_direction: str = "N",
        user_rooms: Optional[List[Dict[str, Any]]] = None,
        has_lift: bool = False,
        has_balcony: bool = False,
        has_verandah: bool = False,
        plot_width: Optional[float] = None,
        plot_depth: Optional[float] = None,
    ):
        self.plot_area = plot_area
        self.building_type = building_type
        self.floor_number = floor_number
        self.floors_total = floors_total
        self.entry_direction = entry_direction
        self.user_rooms = user_rooms or []
        self.has_lift = has_lift
        self.has_balcony = has_balcony
        self.has_verandah = has_verandah
        
        # Plot dimensions
        if plot_width and plot_depth:
            self.plot_width = plot_width
            self.plot_depth = plot_depth
        else:
            side = math.sqrt(plot_area)
            self.plot_width = round(side, 1)
            self.plot_depth = round(side, 1)
        
        # Generated data
        self._enriched_rooms: Optional[List[Dict]] = None
        self._metadata: Dict[str, Any] = {}
        
        self.floor_programs: Dict[int, List[Dict]] = {}
        for f in range(self.floors_total + 2):  # 0=ground, 1..N=upper, N+1=roof
            self.floor_programs[f] = self.get_floor_program(f, self.floors_total)
    
    @property
    def is_ground_floor(self) -> bool:
        return self.floor_number == 0
    
    @property
    def is_multi_floor(self) -> bool:
        return self.floors_total > 1
    
    @property
    def floor_key(self) -> str:
        return 'ground_floor' if self.is_ground_floor else 'upper_floor'
    
    def get_floor_label(self, floor_number: Optional[int] = None) -> str:
        """Returns the label like 'GROUND FLOOR PLAN' or '3RD FLOOR PLAN'."""
        f = floor_number if floor_number is not None else self.floor_number
        if f == 0:
            return "GROUND FLOOR PLAN"
            
        # The top floor (+1) is always the ROOF
        if f >= self.floors_total:
            return "ROOF PLAN"
        
        suffix_map = {1: 'ST', 2: 'ND', 3: 'RD'}
        suffix = suffix_map.get(f, 'TH')
        return f"{f}{suffix} FLOOR PLAN"

    def get_floor_program(self, floor_number: int, floors_total: int) -> List[Dict]:
        """Returns the CORRECT room list for each floor type (G+1 Residential Standard)."""
        rooms = []
        is_single_story = floors_total <= 1
        is_independent = self.building_type == BuildingType.INDEPENDENT_HOUSE
        
        # Room normalizer helper for filtering
        def _norm(rtype):
            return rtype.lower().replace(' ', '_').replace('_room', '')

        if floor_number == 0:
            # GROUND FLOOR: Public zone — hardcoded to real-world AutoCAD standard dimensions
            # Based on: 30'×50' plot, buildable ~24'×44' after setbacks
            # Circulation sequence: Entry Gate → Foyer (6'×8') → Living (12'×14') → Dining (10'×10') → Kitchen (10'×8', rear)
            
            rooms.append({'type': 'car_parking',  'count': 1, 'area_hint': 200, 'label': 'CAR PORCH',
                          'notes': '11\'×15\' standard car porch'})              # 165 sqft
            rooms.append({'type': 'foyer',        'count': 1, 'area_hint': 48,  'label': 'FOYER',
                          'notes': '6\'×8\' entry foyer'})                       # 48 sqft
            rooms.append({'type': 'staircase',    'count': 1, 'area_hint': 70,  'label': 'STAIRCASE',
                          'notes': '7\'×10\' with 10" treads × 13 risers'})     # 70 sqft
            
            if self.has_lift:
                rooms.append({'type': 'lift', 'count': 1, 'area_hint': 25, 'label': 'LIFT'})

            # NOTE: sump and septic are EXTERNAL — keep is_external flag
            rooms.append({'type': 'sump',         'count': 1, 'area_hint': 24,  'is_external': True, 'label': 'SUMP'})
            rooms.append({'type': 'septic_tank',  'count': 1, 'area_hint': 24,  'is_external': True, 'label': 'SEPTIC'})
            
            # 3. Pull Public rooms from user_rooms if available
            public_types = ['living', 'dining', 'kitchen', 'guest_bath', 'bathroom', 'toilet', 'wc', 'pooja', 'utility', 'wash']
            
            added_types = set()
            for r in self.user_rooms:
                ntype = _norm(r['type'])
                if ntype in public_types and 'bedroom' not in ntype:
                    # Limit to 1 bathroom on GF for G+1 unless explicitly requested more than 1 bath total
                    if ntype in ['bathroom', 'toilet', 'wc'] and 'bathroom' in added_types:
                        continue
                    rooms.append(r.copy())
                    added_types.add(ntype)

            # Ensure minimal Public core if not in user_rooms
            if 'living' not in added_types:
                rooms.append({'type': 'Living Room', 'count': 1, 'area_hint': 220, 'label': 'LIVING'}) # 12x18+
            if 'kitchen' not in added_types:
                rooms.append({'type': 'Kitchen', 'count': 1, 'area_hint': 80, 'label': 'KITCHEN'})
            if 'dining' not in added_types:
                rooms.append({'type': 'Dining', 'count': 1, 'area_hint': 100, 'label': 'DINING'})

        elif floor_number == 1 and not is_single_story:
            # 1ST FLOOR: PRIVATE ZONE (Dynamic based on BHK)
            rooms.append({'type': 'passage',   'count': 1, 'area_hint': 60,  'label': 'CORRIDOR',
                          'notes': '4\'×15\' spine corridor — min 4ft clear width required'})
            rooms.append({'type': 'staircase', 'count': 1, 'area_hint': 70,  'label': 'STAIRCASE',
                          'notes': 'Vertical alignment — same XY as ground floor staircase'})
            
            if self.has_lift:
                rooms.append({'type': 'lift', 'count': 1, 'area_hint': 25, 'label': 'LIFT'})

            # Count total bedrooms from user request to determine density
            requested_bedrooms = sum(r.get('count', 1) for r in self.user_rooms if 'bedroom' in r['type'].lower())
            if requested_bedrooms == 0: requested_bedrooms = 2 # Default to 2BHK upper if unknown
            
            # 1. Master Bedroom & Bath (Front) - Always present
            rooms.append({'type': 'bedroom',   'count': 1, 'area_hint': 154, 'label': 'MASTER BEDROOM',
                          'notes': '11\'×14\' master — road-facing for ventilation'})
            rooms.append({'type': 'bathroom',  'count': 1, 'area_hint': 40,  'label': 'MASTER BATH',
                          'notes': '5\'×8\' attached to master'})
            if self.has_balcony:
                rooms.append({'type': 'balcony', 'count': 1, 'area_hint': 24, 'label': 'BALCONY'})
            
            # 2. Second Bedroom (Rear) - Present if 2BHK+
            if requested_bedrooms >= 2:
                rooms.append({'type': 'bedroom', 'count': 1, 'area_hint': 120, 'label': 'BEDROOM 2'})
                rooms.append({'type': 'bathroom', 'count': 1, 'area_hint': 35, 'label': 'BATHROOM 2'})
            
            # 3. Third Bedroom / Common Bath (Rear) - Only if 3BHK+
            if requested_bedrooms >= 3:
                rooms.append({'type': 'bedroom', 'count': 1, 'area_hint': 120, 'label': 'BEDROOM 3'})
                rooms.append({'type': 'bathroom', 'count': 1, 'area_hint': 35, 'label': 'COMMON BATH'})
            elif requested_bedrooms == 2:
                # If 2BHK, add a Study or Open Terrace niche instead of a 3rd bath
                rooms.append({'type': 'study', 'count': 1, 'area_hint': 80, 'label': 'STUDY/OFFICE'})

        elif floor_number >= floors_total:
            # ROOF FLOOR
            rooms.append({'type': 'overhead_water_tank', 'count': 1, 'area_hint': 16,
                          'label': 'OHT',   'notes': '4\'×4\' overhead tank at NE corner'})
            rooms.append({'type': 'stair_room',          'count': 1, 'area_hint': 56,
                          'label': 'MUMTY', 'notes': '7\'×8\' staircase exit room'})
            rooms.append({'type': 'open_terrace',        'count': 1,
                          'area_hint': max(100, self.plot_area - 200),
                          'label': 'OPEN TERRACE',
                          'notes': 'Remaining roof slab with 3\' parapet wall'})
            
        else:
            # Fallback for Generic Upper Floors (N > 1)
            rooms = [r.copy() for r in self.user_rooms]
            rooms.append({'type': 'passage', 'count': 1, 'area_hint': 40})
            rooms.append({'type': 'staircase', 'count': 1, 'area_hint': 50})
                
        return rooms
    
    def get_enriched_rooms(self) -> List[Dict[str, Any]]:
        """
        Returns the complete room list with mandatory elements injected.
        
        This is the room list that should be passed to the BSP engine.
        It includes all user-requested rooms PLUS auto-injected elements
        like passages, staircases, and lift shafts.
        """
        if self._enriched_rooms is not None:
            return self._enriched_rooms
        
        rooms = list(self.user_rooms)
        
        # 1. Inject mandatory elements for this building type + floor
        rooms = self._inject_mandatory_elements(rooms)
        
        # 2. Inject staircase if multi-floor
        if self.is_multi_floor:
            rooms = self._inject_staircase(rooms)
        
        # 3. Inject lift if requested
        if self.has_lift:
            rooms = self._inject_lift(rooms)
        
        # 4. Inject verandah/balcony if requested
        if self.has_verandah or self.has_balcony:
            rooms = self._inject_verandah(rooms)
        
        # 5. Store metadata
        self._metadata = {
            'building_type': self.building_type,
            'floor_number': self.floor_number,
            'floor_label': self.get_floor_label(),
            'entry_direction': self.entry_direction,
            'total_rooms': len(rooms),
            'has_passage': any(r['type'].lower() == 'passage' for r in rooms),
            'has_staircase': any(r['type'].lower() == 'staircase' for r in rooms),
            'has_lift': any(r['type'].lower() == 'lift' for r in rooms),
        }
        
        self._enriched_rooms = rooms
        return rooms
    
    def get_metadata(self) -> Dict[str, Any]:
        """Returns metadata about the building program (for title block etc)."""
        if not self._enriched_rooms:
            self.get_enriched_rooms()
        return self._metadata
    
    def _inject_mandatory_elements(self, rooms: List[Dict]) -> List[Dict]:
        """Adds mandatory elements for the building type."""
        building_config = MANDATORY_ELEMENTS.get(self.building_type, {})
        floor_elements = building_config.get(self.floor_key, [])
        
        for element in floor_elements:
            etype = element['type'].lower()
            
            # Don't duplicate if already present
            existing = [r for r in rooms if r['type'].lower() == etype]
            if existing:
                continue
            
            # Calculate area
            if 'fixed_area' in element:
                area = element['fixed_area']
            else:
                area = max(
                    element.get('min_area', 30),
                    self.plot_area * element.get('max_area_pct', 0.08)
                )
            
            rooms.append({
                'type': element['type'],
                'count': element['count'],
                'area_hint': area,
                'is_mandatory': True,
                'notes': element.get('notes', ''),
            })
        
        return rooms
    
    def _inject_staircase(self, rooms: List[Dict]) -> List[Dict]:
        """Adds staircase if not already present."""
        has_stairs = any(r['type'].lower() in ['staircase', 'stairs'] for r in rooms)
        if has_stairs:
            return rooms
        
        # Standard staircase: ~50 sqft (3'-6" x 14'-0" typical)
        rooms.append({
            'type': 'Staircase',
            'count': 1,
            'area_hint': 50,
            'is_mandatory': True,
            'notes': 'Auto-injected for multi-floor building',
        })
        return rooms
    
    def _inject_lift(self, rooms: List[Dict]) -> List[Dict]:
        """Adds lift shaft if not already present."""
        has_lift = any(r['type'].lower() == 'lift' for r in rooms)
        if has_lift:
            return rooms
        
        # Lift shaft: ~25 sqft (5' x 5')
        rooms.append({
            'type': 'Lift',
            'count': 1,
            'area_hint': 25,
            'is_mandatory': True,
            'notes': 'Lift shaft',
        })
        return rooms
    
    def _inject_verandah(self, rooms: List[Dict]) -> List[Dict]:
        """Adds verandah/balcony."""
        has_verandah = any(r['type'].lower() in ['verandah', 'balcony'] for r in rooms)
        if has_verandah:
            return rooms
        
        label = 'Verandah' if self.has_verandah else 'Balcony'
        # Verandah: ~3.5ft deep × plot width, or ~60-80 sqft
        area = min(self.plot_width * 3.5, 80)
        
        rooms.append({
            'type': label,
            'count': 1,
            'area_hint': area,
            'is_mandatory': True,
            'notes': f'{label} on {self.entry_direction}-facing side',
        })
        return rooms
    
    # ── DOOR BUDGET ─────────────────────────────────────────────
    
    def should_place_door(self, room1_type: str, room2_type: str) -> Optional[Dict]:
        """
        Checks if a door should be placed between two room types.
        
        Returns:
            Door config dict if yes, None if no door.
        """
        t1 = self._normalize_room_type(room1_type)
        t2 = self._normalize_room_type(room2_type)
        pair = frozenset({t1, t2})
        
        # Check forbidden first
        if pair in NO_DOOR_PAIRS:
            return None
        
        # Check same-type pairs (bedroom↔bedroom = no door)
        if t1 == t2 and t1 not in ('passage', 'hallway'):
            return None
        
        # Check allowed pairs
        door_config = DOOR_ALLOWED_PAIRS.get(pair)
        if door_config:
            return door_config
        
        # Default: no door for unlisted pairs
        return None
    
    def get_window_budget(self, room_type: str) -> Dict:
        """
        Returns window allocation for a room type.
        
        Returns:
            Dict with 'count', 'width', 'type'
        """
        t = self._normalize_room_type(room_type)
        return WINDOW_BUDGET.get(t, {'count': 0, 'width': 0, 'type': 'none'})
    
    def get_adjacency_preferences(self) -> Tuple[List, List]:
        """Returns (preferred_adjacency, forbidden_adjacency) tuples."""
        return PREFERRED_ADJACENCY, FORBIDDEN_ADJACENCY
    
    def get_entry_wall_side(self) -> str:
        """
        Returns which side of the plot boundary the entry should be on.
        Maps entry_direction to plot edge.
        
        If entry_direction is 'E', the entry is on the East (right) wall.
        """
        direction_to_side = {
            'N': 'top', 'S': 'bottom', 'E': 'right', 'W': 'left',
            'NE': 'top', 'NW': 'top', 'SE': 'bottom', 'SW': 'bottom',
        }
        return direction_to_side.get(self.entry_direction, 'bottom')
    
    @staticmethod
    def _normalize_room_type(rtype: str) -> str:
        """Normalizes room type for lookup."""
        t = rtype.lower().replace(' ', '_')
        # Strip common suffixes but keep prefixes like 'master_'
        t = t.replace('_room', '')
        # Map common aliases
        aliases = {
            'bed_room': 'bedroom',
            'bath_room': 'bathroom',
            'living_room': 'living',
            'dining_room': 'dining',
            'wash_room': 'bathroom',
            'toilet': 'bathroom',
            'wc': 'bathroom',
            'hall': 'hallway',
            'corridor': 'passage',
            'stairs': 'staircase',
            'elevator': 'lift',
            'balcony': 'verandah',
            'porch': 'verandah',
            'prayer': 'pooja',
            'mandir': 'pooja',
        }
        return aliases.get(t, t)


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def create_building_program(
    plot_area: float,
    user_rooms: List[Dict],
    building_type: str = BuildingType.INDEPENDENT_HOUSE,
    floor_number: int = 0,
    floors_total: int = 1,
    entry_direction: str = "N",
    has_lift: bool = False,
    has_balcony: bool = False,
    has_verandah: bool = False,
    plot_width: Optional[float] = None,
    plot_depth: Optional[float] = None,
) -> BuildingProgram:
    """
    Factory function to create a BuildingProgram.
    
    Usage:
        program = create_building_program(
            plot_area=2000,
            user_rooms=[{'type': 'Bedroom', 'count': 3}, ...],
            building_type='apartment',
            floor_number=3,
            entry_direction='E',
            has_lift=True
        )
        rooms = program.get_enriched_rooms()
    """
    program = BuildingProgram(
        plot_area=plot_area,
        building_type=building_type,
        floor_number=floor_number,
        floors_total=floors_total,
        entry_direction=entry_direction,
        user_rooms=user_rooms,
        has_lift=has_lift,
        has_balcony=has_balcony,
        has_verandah=has_verandah,
        plot_width=plot_width,
        plot_depth=plot_depth,
    )
    
    # Removed global override of user_rooms to prevent leakage between floors.
    # The caller should use program.get_floor_program(num, total).
    
    return program


# ═══════════════════════════════════════════════════════════════════════
# FLOOR LAYOUT GENERATORS (fixed-position, no BSP needed)
# ═══════════════════════════════════════════════════════════════════════

def generate_ground_floor_layout(
    plot_width: float,
    plot_depth: float,
    has_lift: bool = False,
) -> List[Dict[str, Any]]:
    """
    Ground floor: parking bay + staircase + lift (if present).
    No BSP needed — positions are fixed per blueprint conventions.
    Dimensions in feet (plot_width/plot_depth are in feet).
    """
    # Staircase: 2.075 M × 2.075 M → feet
    stair_w = round(2.075 / 0.3048, 2)  # ≈ 6.81 ft
    stair_h = round(2.075 / 0.3048, 2)

    stair = {
        'id': 'staircase_0', 'type': 'staircase',
        'x': round(plot_width * 0.7, 2),  # Move to a standard corner for alignment
        'y': round(plot_depth * 0.1, 2),
        'width': stair_w, 'height': stair_h,
        'area': round(stair_w * stair_h, 1),
        'floor': 0,
    }

    lift = None
    if has_lift:
        # Lift: 1.2 M × 1.2 M → ≈ 3.937 ft
        lift = {
            'id': 'lift_0', 'type': 'lift',
            'x': round(stair['x'] + stair['width'], 2),
            'y': stair['y'],
            'width': 3.937, 'height': 3.937,
            'area': round(3.937 * 3.937, 1),
            'floor': 0,
        }

    parking = {
        'id': 'parking_0', 'type': 'car_parking',
        'x': 0, 'y': 0,
        'width': plot_width, 'height': plot_depth,
        'area': round(plot_width * plot_depth, 1),
        'floor': 0,
    }

    return [r for r in [parking, stair, lift] if r is not None]


def generate_roof_floor_layout(
    plot_width: float,
    plot_depth: float,
    has_lift: bool = False,
    roof_floor_num: int = 99,
    fixed_positions: dict = None
) -> List[Dict[str, Any]]:
    """
    Roof floor: overhead water reservoir + open terrace + lift machine room.
    Dimensions in feet.
    """
    rooms = []
    machine_room = None
    
    # ── 1. MUMTY / STAIR ROOM (Vertical alignment with typical floors) ──
    stair_room = None
    if fixed_positions and 'staircase' in fixed_positions:
        pos = fixed_positions['staircase']
        stair_room = {
            'id': 'stair_room', 'type': 'stair_room',
            'x': pos['x'], 'y': pos['y'],
            'width': pos['width'], 'height': pos['height'],
            'area': round(pos['width'] * pos['height'], 1),
            'floor': roof_floor_num,
        }
        rooms.append(stair_room)

    # ── 2. OHWR ────────────────────────────────────────────────────────
    ohwr = {
        'id': 'ohwr', 'type': 'overhead_water_tank',
        'x': round(plot_width - 8.28, 2),   # NE corner (rear of typical N-facing plot)
        'y': round(plot_depth - 8.28, 2),
        'width': 8.28, 'height': 8.28,
        'area': round(8.28 * 8.28, 1),
        'floor': roof_floor_num,
    }
    rooms.append(ohwr)

    # ── 4. TERRACE ─────────────────────────────────────────────────────
    terrace = {
        'id': 'terrace', 'type': 'open_terrace',
        'x': 0, 'y': 0,
        'width': plot_width, 'height': plot_depth,
        'area': round(plot_width * plot_depth, 1),
        'floor': roof_floor_num,
        'is_annotation': True
    }
    rooms.append(terrace)   # Terrace renders LAST (bottommost SVG layer, covered by OHT/MUMTY)

    # ── 3. MACHINE ROOM (For Lift) ─────────────────────────────────────
    if has_lift:
        if fixed_positions and 'lift' in fixed_positions:
            pos = fixed_positions['lift']
            machine_room = {
                'id': 'lift_mroom', 'type': 'lift_machine_room',
                'x': pos['x'], 'y': pos['y'],
                'width': pos['width'], 'height': pos['height'],
                'area': round(pos['width'] * pos['height'], 1),
                'floor': roof_floor_num,
            }
        else:
            machine_room = {
                'id': 'lift_mroom', 'type': 'lift_machine_room',
                'x': 8.5, 'y': 0,
                'width': 6.32, 'height': 8.45,
                'area': round(6.32 * 8.45, 1),
                'floor': roof_floor_num,
            }
        rooms.append(machine_room)

    return rooms