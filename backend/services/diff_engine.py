"""
Diff Engine — Feature D: Refinement Diffing
============================================
Compares two room layouts and computes the minimal set of changes
needed to transform one into the other.

This allows the frontend to:
1. Highlight only the changed rooms in the UI
2. Patch the SVG surgically instead of re-rendering everything
3. Show an animated "before/after" transition

DiffResult categories:
  - moved:    Room exists in both, but position changed
  - resized:  Room exists in both, but dimensions changed
  - added:    Room exists in new layout but not old
  - removed:  Room exists in old layout but not new
  - unchanged: Room is identical in both layouts
"""
import logging

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class RoomChange:
    room_id: str
    room_type: str
    change_type: str  # "moved" | "resized" | "added" | "removed" | "unchanged"
    old_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    delta: Optional[Dict[str, Any]] = None  # What specifically changed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "room_id": self.room_id,
            "room_type": self.room_type,
            "change_type": self.change_type,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "delta": self.delta,
        }


@dataclass
class DiffResult:
    moved: List[RoomChange] = field(default_factory=list)
    resized: List[RoomChange] = field(default_factory=list)
    added: List[RoomChange] = field(default_factory=list)
    removed: List[RoomChange] = field(default_factory=list)
    unchanged: List[RoomChange] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return len(self.moved) + len(self.resized) + len(self.added) + len(self.removed)

    @property
    def is_identical(self) -> bool:
        return self.total_changes == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "moved": [c.to_dict() for c in self.moved],
            "resized": [c.to_dict() for c in self.resized],
            "added": [c.to_dict() for c in self.added],
            "removed": [c.to_dict() for c in self.removed],
            "unchanged": [c.to_dict() for c in self.unchanged],
            "total_changes": self.total_changes,
            "is_identical": self.is_identical,
            "summary": _build_summary(self),
        }


def _build_summary(diff: "DiffResult") -> str:
    parts = []
    if diff.added:
        parts.append(f"{len(diff.added)} room(s) added")
    if diff.removed:
        parts.append(f"{len(diff.removed)} room(s) removed")
    if diff.moved:
        parts.append(f"{len(diff.moved)} room(s) moved")
    if diff.resized:
        parts.append(f"{len(diff.resized)} room(s) resized")
    if not parts:
        return "No changes — layouts are identical"
    return "; ".join(parts)


# ── POSITION TOLERANCE ────────────────────────────────────────────────────────

POSITION_TOLERANCE = 1.0   # feet — changes smaller than this are "unchanged"
SIZE_TOLERANCE = 2.0        # feet — size changes smaller than this are "unchanged"


def _rooms_same_position(a: Dict, b: Dict) -> bool:
    return (abs(a.get("x", 0) - b.get("x", 0)) < POSITION_TOLERANCE and
            abs(a.get("y", 0) - b.get("y", 0)) < POSITION_TOLERANCE)


def _rooms_same_size(a: Dict, b: Dict) -> bool:
    return (abs(a.get("width", 0) - b.get("width", 0)) < SIZE_TOLERANCE and
            abs(a.get("height", 0) - b.get("height", 0)) < SIZE_TOLERANCE)


# ── DIFF COMPUTATION ──────────────────────────────────────────────────────────

def compute_diff(
    old_layout: List[Dict[str, Any]],
    new_layout: List[Dict[str, Any]]
) -> DiffResult:
    """
    Computes the diff between two room layouts.

    Matching strategy:
    1. Match rooms by ID first (same room, different position/size)
    2. For unmatched rooms, try matching by type (room added/removed of same type)
    3. Remaining unmatched old rooms → removed; unmatched new rooms → added

    Args:
        old_layout: Previous list of placed room dicts
        new_layout: New list of placed room dicts

    Returns:
        DiffResult with categorized changes
    """
    diff = DiffResult()

    old_by_id: Dict[str, Dict] = {r["id"]: r for r in old_layout}
    new_by_id: Dict[str, Dict] = {r["id"]: r for r in new_layout}

    matched_old_ids = set()
    matched_new_ids = set()

    # Pass 1: Match by ID
    for room_id in set(old_by_id.keys()) & set(new_by_id.keys()):
        old_room = old_by_id[room_id]
        new_room = new_by_id[room_id]

        same_pos = _rooms_same_position(old_room, new_room)
        same_size = _rooms_same_size(old_room, new_room)

        if same_pos and same_size:
            diff.unchanged.append(RoomChange(
                room_id=room_id,
                room_type=new_room.get("type", ""),
                change_type="unchanged",
                old_state=old_room,
                new_state=new_room,
            ))
        elif not same_pos and same_size:
            delta = {
                "dx": round(new_room.get("x", 0) - old_room.get("x", 0), 2),
                "dy": round(new_room.get("y", 0) - old_room.get("y", 0), 2),
            }
            diff.moved.append(RoomChange(
                room_id=room_id,
                room_type=new_room.get("type", ""),
                change_type="moved",
                old_state=old_room,
                new_state=new_room,
                delta=delta,
            ))
        elif same_pos and not same_size:
            delta = {
                "dw": round(new_room.get("width", 0) - old_room.get("width", 0), 2),
                "dh": round(new_room.get("height", 0) - old_room.get("height", 0), 2),
                "da": round(new_room.get("area", 0) - old_room.get("area", 0), 2),
            }
            diff.resized.append(RoomChange(
                room_id=room_id,
                room_type=new_room.get("type", ""),
                change_type="resized",
                old_state=old_room,
                new_state=new_room,
                delta=delta,
            ))
        else:
            # Both moved and resized — classify as moved (more impactful)
            delta = {
                "dx": round(new_room.get("x", 0) - old_room.get("x", 0), 2),
                "dy": round(new_room.get("y", 0) - old_room.get("y", 0), 2),
                "dw": round(new_room.get("width", 0) - old_room.get("width", 0), 2),
                "dh": round(new_room.get("height", 0) - old_room.get("height", 0), 2),
            }
            diff.moved.append(RoomChange(
                room_id=room_id,
                room_type=new_room.get("type", ""),
                change_type="moved",
                old_state=old_room,
                new_state=new_room,
                delta=delta,
            ))

        matched_old_ids.add(room_id)
        matched_new_ids.add(room_id)

    # Pass 2: Unmatched old rooms → removed
    for room_id, room in old_by_id.items():
        if room_id not in matched_old_ids:
            diff.removed.append(RoomChange(
                room_id=room_id,
                room_type=room.get("type", ""),
                change_type="removed",
                old_state=room,
                new_state=None,
            ))

    # Pass 3: Unmatched new rooms → added
    for room_id, room in new_by_id.items():
        if room_id not in matched_new_ids:
            diff.added.append(RoomChange(
                room_id=room_id,
                room_type=room.get("type", ""),
                change_type="added",
                old_state=None,
                new_state=room,
            ))

    return diff


# ── SVG PATCHING ──────────────────────────────────────────────────────────────

def apply_diff_to_svg(original_svg: str, diff: DiffResult) -> str:
    """
    Surgically patches an SVG string based on a DiffResult.

    For each changed room, finds the corresponding SVG group element
    (identified by data-room-id attribute) and updates its transform/dimensions.

    Note: This requires the SVG renderer to emit groups with data-room-id attributes.
    If the attribute is missing, falls back to returning the original SVG unchanged.

    Args:
        original_svg: The full SVG string from the previous generation
        diff: The computed DiffResult

    Returns:
        Patched SVG string with only changed rooms updated
    """
    if diff.is_identical:
        return original_svg

    svg = original_svg

    # Process moved rooms — update translate() in transform attribute
    for change in diff.moved:
        if change.new_state is None:
            continue
        room_id = change.room_id
        new_x = change.new_state.get("x", 0)
        new_y = change.new_state.get("y", 0)

        # Pattern: <g data-room-id="bedroom_1" transform="translate(...)">
        pattern = rf'(<g[^>]*data-room-id="{re.escape(room_id)}"[^>]*transform=")translate\([^)]+\)'
        replacement = rf'\g<1>translate({new_x}, {new_y})'
        svg = re.sub(pattern, replacement, svg)

    # Process removed rooms — comment them out
    for change in diff.removed:
        room_id = change.room_id
        pattern = rf'<g[^>]*data-room-id="{re.escape(room_id)}"[^>]*>.*?</g>'
        svg = re.sub(pattern, f'<!-- REMOVED: {room_id} -->', svg, flags=re.DOTALL)

    return svg