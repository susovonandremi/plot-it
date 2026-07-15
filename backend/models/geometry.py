# backend/models/geometry.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
import math

class Orientation(Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"

class WallType(Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    PARTY = "party"
    SETBACK = "setback"

@dataclass(frozen=True)
class Vec2:
    """Immutable 2D vector in feet-space with architectural operations."""
    x: float
    y: float

    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> Vec2:
        return Vec2(self.x * scalar, self.y * scalar)

    def dot(self, other: Vec2) -> float:
        return self.x * other.x + self.y * other.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalized(self) -> Vec2:
        L = self.length()
        return Vec2(self.x / L, self.y / L) if L > 0 else Vec2(0, 0)

    def perpendicular(self) -> Vec2:
        """90° counter-clockwise rotation."""
        return Vec2(-self.y, self.x)

    def rotate(self, degrees: float) -> Vec2:
        """Rotate vector by degrees (counter-clockwise)."""
        rad = math.radians(degrees)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        return Vec2(
            self.x * cos_r - self.y * sin_r,
            self.x * sin_r + self.y * cos_r
        )

@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in feet-space."""
    x: float
    y: float
    width: float
    height: float

    @property
    def x2(self) -> float:
        return self.x + self.width

    @property
    def y2(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Vec2:
        return Vec2(self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        min_dim = min(self.width, self.height)
        return max(self.width, self.height) / min_dim if min_dim > 0 else float('inf')

    def intersects(self, other: BBox, margin: float = 0.0) -> bool:
        return not (
            self.x2 + margin <= other.x or
            other.x2 + margin <= self.x or
            self.y2 + margin <= other.y or
            other.y2 + margin <= self.y
        )

    def contains_point(self, p: Vec2) -> bool:
        return self.x <= p.x <= self.x2 and self.y <= p.y <= self.y2

    def expanded(self, margin: float) -> BBox:
        return BBox(
            self.x - margin,
            self.y - margin,
            self.width + 2 * margin,
            self.height + 2 * margin
        )

@dataclass
class WallSegment:
    id: str
    start: Vec2
    end: Vec2
    orientation: Orientation
    wall_type: WallType
    thickness_ft: float
    adjacent_room_ids: List[str] = field(default_factory=list)
    has_opening: bool = False

    @property
    def length(self) -> float:
        return (self.end - self.start).length()

    @property
    def midpoint(self) -> Vec2:
        return Vec2((self.start.x + self.end.x) / 2, (self.start.y + self.end.y) / 2)

    @property
    def direction(self) -> Vec2:
        return (self.end - self.start).normalized()

    @property
    def normal(self) -> Vec2:
        return self.direction.perpendicular()

@dataclass
class DoorPlacement:
    id: str
    room1_id: str
    room2_id: str
    door_type: str            # "internal", "main_entry", "french", etc.
    width_ft: float
    position: Vec2            # Center of door on wall
    orientation: Orientation
    swing_direction: str      # "into_room1", "into_room2"
    wall_segment_id: str
    rotation_deg: float = 0.0

@dataclass
class WindowPlacement:
    id: str
    room_id: str
    window_type: str          # "standard", "ventilator", "french"
    width_ft: float
    position: Vec2
    orientation: Orientation
    side: str                 # "top", "bottom", "left", "right"
    wall_segment_id: str

@dataclass
class Room:
    id: str
    type: str
    label: str
    bbox: BBox
    vastu_zone: str = ""
    floor_material: str = ""
    is_annotation: bool = False

def normalize_room_type(rtype: str) -> str:
    """Canonical normalization function for room type strings."""
    t = rtype.lower().strip().replace(' ', '_')
    # Strip suffixes
    if t.endswith('_room'):
        t = t[:-5]
    elif t.endswith('room'):
        t = t[:-4]
    
    # Common mappings to canonical types
    aliases = {
        'bed': 'bedroom',
        'master_bed': 'master_bedroom',
        'bath': 'bathroom',
        'toilet': 'bathroom',
        'wc': 'bathroom',
        'washroom': 'bathroom',
        'powder': 'bathroom',
        'living_room': 'living',
        'dining_room': 'dining',
        'hall': 'hallway',
        'corridor': 'passage',
        'stairs': 'staircase',
        'elevator': 'lift',
        'balcony': 'verandah',
        'porch': 'verandah',
        'prayer': 'pooja',
        'family': 'living',
        'lounge': 'living',
        'drawing': 'living',
        'store': 'store_room',
        'utility': 'utility_room',
    }
    return aliases.get(t, t)
