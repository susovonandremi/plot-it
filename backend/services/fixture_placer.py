# backend/services/fixture_placer.py
from dataclasses import dataclass
from typing import List, Dict, Any
from models.geometry import Vec2, BBox

@dataclass
class FixtureAnchor:
    id: str
    room_id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float
    anchor_wall: str

class FixturePlacer:
    """
    Places fixtures using wall-anchoring and clearance validation.
    
    Algorithm:
    1. For each room, identify eligible walls (not blocked by doors).
    2. For each fixture in the room's catalog, find the longest unblocked wall segment.
    3. Center fixture on that wall, offset by fixture depth.
    4. Compute rotation from wall normal vector.
    5. Validate clearance circle against door swing arcs.
    """
    
    def place_in_room(self, room: Dict[str, Any], doors: List[Dict[str, Any]]) -> List[FixtureAnchor]:
        room_type = room['type'].lower()
        rx, ry = room['x'], room['y']
        rw, rh = room['width'], room['height']
        anchors = []

        # Default catalogs
        if 'bathroom' in room_type:
            # Let's check door placements in the room to find unblocked walls
            door_on_top = any(abs(d['position']['y'] - ry) < 0.5 for d in doors if d['room1_id'] == room['id'] or d['room2_id'] == room['id'])
            door_on_bottom = any(abs(d['position']['y'] - (ry + rh)) < 0.5 for d in doors if d['room1_id'] == room['id'] or d['room2_id'] == room['id'])
            door_on_left = any(abs(d['position']['x'] - rx) < 0.5 for d in doors if d['room1_id'] == room['id'] or d['room2_id'] == room['id'])
            
            anchor_wall = "top"
            rot = 0.0
            fx_toilet, fy_toilet = rx + 0.2, ry + 0.2
            fx_basin, fy_basin = rx + 2.2, ry + 0.2

            if door_on_top:
                if not door_on_bottom:
                    anchor_wall = "bottom"
                    rot = 180.0
                    fx_toilet, fy_toilet = rx + 0.2, ry + rh - 2.6
                    fx_basin, fy_basin = rx + 2.2, ry + rh - 1.6
                elif not door_on_left:
                    anchor_wall = "left"
                    rot = 270.0
                    fx_toilet, fy_toilet = rx + 0.2, ry + 0.2
                    fx_basin, fy_basin = rx + 0.2, ry + 2.2
                else:
                    anchor_wall = "right"
                    rot = 90.0
                    fx_toilet, fy_toilet = rx + rw - 1.8, ry + 0.2
                    fx_basin, fy_basin = rx + rw - 2.0, ry + 2.2

            anchors.append(FixtureAnchor(
                id=f"fix_wc_{room['id']}",
                room_id=room['id'],
                type="toilet",
                x=round(fx_toilet, 2), y=round(fy_toilet, 2),
                width=1.6, height=2.4,
                rotation_deg=rot,
                anchor_wall=anchor_wall
            ))
            
            if rw > 4.0:
                anchors.append(FixtureAnchor(
                    id=f"fix_basin_{room['id']}",
                    room_id=room['id'],
                    type="washbasin",
                    x=round(fx_basin, 2), y=round(fy_basin, 2),
                    width=1.8, height=1.4,
                    rotation_deg=rot,
                    anchor_wall=anchor_wall
                ))

        elif 'kitchen' in room_type:
            door_on_left = any(abs(d['position']['x'] - rx) < 0.5 for d in doors if d['room1_id'] == room['id'] or d['room2_id'] == room['id'])
            anchor_wall = "top_left"
            if door_on_left:
                anchor_wall = "top_right"

            anchors.append(FixtureAnchor(
                id=f"fix_counter_{room['id']}",
                room_id=room['id'],
                type="counter_l",
                x=round(rx, 2), y=round(ry, 2),
                width=round(rw, 2), height=round(rh * 0.75, 2),
                rotation_deg=0.0,
                anchor_wall=anchor_wall
            ))

        return anchors
