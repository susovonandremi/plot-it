# backend/tests/test_label_fixture_placers.py
import pytest
from shapely.geometry import box as shapely_box
from services.label_placer import LabelPlacer, LabelResult
from services.fixture_placer import FixturePlacer

def test_label_placer():
    rooms = [
        {'id': 'living_1', 'type': 'living', 'x': 0.0, 'y': 0.0, 'width': 12.0, 'height': 15.0, 'label': 'LIVING'},
        {'id': 'bed_1', 'type': 'bedroom', 'x': 0.0, 'y': 15.0, 'width': 10.0, 'height': 10.0, 'label': 'BEDROOM'},
    ]
    
    wall_boundary = shapely_box(0, 0, 12, 25)
    placer = LabelPlacer(rooms, wall_boundary)
    results = placer.place_all()
    
    assert len(results) == 2
    
    # Assert font sizing and placement bounds
    for r in results:
        assert r.room_id in ['living_1', 'bed_1']
        assert r.font_px in [10.0, 8.0, 6.5, 5.0]
        # Bounding box should reside within room coordinates
        room = next(rm for rm in rooms if rm['id'] == r.room_id)
        assert r.bbox.x >= room['x']
        assert r.bbox.y >= room['y']
        assert r.bbox.x + r.bbox.width <= room['x'] + room['width']
        assert r.bbox.y + r.bbox.height <= room['y'] + room['height']

def test_fixture_placer_bathroom():
    room = {'id': 'bath_1', 'type': 'bathroom', 'x': 5.0, 'y': 5.0, 'width': 8.0, 'height': 6.0}
    
    # Mock door on left side
    doors = [
        {'room1_id': 'bath_1', 'room2_id': 'bed_1', 'position': {'x': 5.0, 'y': 6.0}, 'orientation': 'vertical', 'width': 3.0}
    ]
    
    placer = FixturePlacer()
    fixtures = placer.place_in_room(room, doors)
    
    assert len(fixtures) >= 1
    toilet = next(f for f in fixtures if f.type == "toilet")
    assert toilet.room_id == "bath_1"
    assert toilet.width == 1.6
    assert toilet.height == 2.4
    
    # Should place toilet away from the left wall where door is located
    assert toilet.anchor_wall in ["top", "bottom", "right"]

def test_fixture_placer_kitchen():
    room = {'id': 'kit_1', 'type': 'kitchen', 'x': 0.0, 'y': 0.0, 'width': 10.0, 'height': 8.0}
    doors = []
    
    placer = FixturePlacer()
    fixtures = placer.place_in_room(room, doors)
    
    assert len(fixtures) == 1
    counter = fixtures[0]
    assert counter.type == "counter_l"
    assert counter.room_id == "kit_1"
    assert counter.width == 10.0
    assert counter.height == 6.0  # 8 * 0.75
