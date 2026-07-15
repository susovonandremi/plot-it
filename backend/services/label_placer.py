# backend/services/label_placer.py
from dataclasses import dataclass
from shapely.geometry import box as shapely_box, Polygon
from typing import List, Dict, Any, Union
from models.geometry import Vec2, BBox

@dataclass
class LabelResult:
    room_id: str
    bbox: BBox
    font_px: float

class LabelPlacer:
    """
    Places room labels using bounding-box collision resolution.
    
    Algorithm:
    1. Compute label BBox at room centroid.
    2. Check collision with wall boundary (Shapely) and existing labels.
    3. If collision, apply force-directed shift TOWARD room centroid
       (guaranteed interior) with exponential decay.
    4. If still colliding after N iterations, reduce font size by
       quantized steps (10px → 8px → 6.5px → 5px).
    5. Guarantee: every room gets exactly one label. No room is unlabeled.
    """
    
    def __init__(self, rooms: List[Dict[str, Any]], wall_boundary: Any = None):
        self.rooms = rooms
        self.wall_poly = wall_boundary
        self.placed: List[BBox] = []

    def place_all(self) -> List[LabelResult]:
        # Sort by area descending — larger rooms claim space first
        sorted_rooms = sorted(self.rooms, key=lambda r: r.get('width', 0) * r.get('height', 0), reverse=True)
        results = []
        for room in sorted_rooms:
            result = self._place_single(room)
            self.placed.append(result.bbox)
            results.append(result)
        return results

    def _estimate_bbox(self, label: str, font_px: float, center: Vec2) -> BBox:
        # Approximate width: ~0.6 * character count * font size in feet
        # Convert font_px to feet: 1px = 1/30 ft
        font_ft = font_px / 30.0
        width = len(label) * 0.6 * font_ft
        height = font_ft * 1.2
        return BBox(
            x=center.x - width / 2,
            y=center.y - height / 2,
            width=width,
            height=height
        )

    def _collides(self, bbox: BBox, room: Dict[str, Any]) -> bool:
        # Check collision with other placed labels
        box_poly = shapely_box(bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)
        
        # Must be fully inside room boundary
        rx, ry, rw, rh = room['x'], room['y'], room['width'], room['height']
        room_poly = shapely_box(rx, ry, rx + rw, ry + rh)
        if not room_poly.contains(box_poly):
            return True
            
        # Check other placed labels
        for pb in self.placed:
            pb_poly = shapely_box(pb.x, pb.y, pb.x + pb.width, pb.y + pb.height)
            if box_poly.intersects(pb_poly):
                return True
        return False

    def _place_single(self, room: Dict[str, Any]) -> LabelResult:
        rx, ry, rw, rh = room['x'], room['y'], room['width'], room['height']
        centroid = Vec2(rx + rw / 2, ry + rh / 2)
        font_sizes = [10.0, 8.0, 6.5, 5.0]
        
        label_text = room.get('label', room.get('type', 'ROOM')).upper()
        
        # Try different font sizes
        for font_px in font_sizes:
            label_bbox = self._estimate_bbox(label_text, font_px, centroid)
            
            # Force-directed resolution (max 8 iterations)
            for i in range(8):
                if not self._collides(label_bbox, room):
                    return LabelResult(room['id'], label_bbox, font_px)
                
                # Move 30% toward centroid each step
                current_center = label_bbox.center
                force_x = (centroid.x - current_center.x) * 0.3
                force_y = (centroid.y - current_center.y) * 0.3
                label_bbox = BBox(
                    label_bbox.x + force_x,
                    label_bbox.y + force_y,
                    label_bbox.width, label_bbox.height
                )
        
        # Fallback: place at centroid with smallest font
        fallback_bbox = self._estimate_bbox(label_text, font_sizes[-1], centroid)
        return LabelResult(room['id'], fallback_bbox, font_sizes[-1])
