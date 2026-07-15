# backend/tests/test_geometry.py
import pytest
import math
from models.geometry import Vec2, BBox, normalize_room_type

def test_vec2_operations():
    v1 = Vec2(3.0, 4.0)
    v2 = Vec2(1.0, 2.0)
    
    # Addition
    v_add = v1 + v2
    assert v_add.x == 4.0
    assert v_add.y == 6.0
    
    # Subtraction
    v_sub = v1 - v2
    assert v_sub.x == 2.0
    assert v_sub.y == 2.0
    
    # Multiplication
    v_mul = v1 * 2.0
    assert v_mul.x == 6.0
    assert v_mul.y == 8.0
    
    # Length & Dot Product
    assert v1.length() == 5.0
    assert v1.dot(v2) == 11.0  # 3*1 + 4*2
    
    # Normalized
    v_norm = v1.normalized()
    assert pytest.approx(v_norm.length()) == 1.0
    assert pytest.approx(v_norm.x) == 0.6
    assert pytest.approx(v_norm.y) == 0.8
    
    # Perpendicular
    v_perp = v1.perpendicular()
    assert v_perp.x == -4.0
    assert v_perp.y == 3.0
    assert v_perp.dot(v1) == 0.0
    
    # Rotate 90 degrees
    v_rot = v1.rotate(90)
    assert pytest.approx(v_rot.x) == -4.0
    assert pytest.approx(v_rot.y) == 3.0

def test_bbox_operations():
    b1 = BBox(0.0, 0.0, 10.0, 10.0)
    b2 = BBox(5.0, 5.0, 10.0, 10.0)
    b3 = BBox(12.0, 12.0, 5.0, 5.0)
    
    assert b1.x2 == 10.0
    assert b1.y2 == 10.0
    assert b1.center == Vec2(5.0, 5.0)
    assert b1.area == 100.0
    assert b1.aspect_ratio == 1.0
    
    # Intersections
    assert b1.intersects(b2) == True
    assert b1.intersects(b3) == False
    
    # Contains point
    assert b1.contains_point(Vec2(5.0, 5.0)) == True
    assert b1.contains_point(Vec2(11.0, 5.0)) == False
    
    # Expanded
    b_exp = b1.expanded(1.0)
    assert b_exp.x == -1.0
    assert b_exp.y == -1.0
    assert b_exp.width == 12.0
    assert b_exp.height == 12.0

def test_normalize_room_type():
    assert normalize_room_type("Bedroom") == "bedroom"
    assert normalize_room_type("Master Bedroom") == "master_bedroom"
    assert normalize_room_type("bath room") == "bathroom"
    assert normalize_room_type("toilet") == "bathroom"
    assert normalize_room_type("wc") == "bathroom"
    assert normalize_room_type("Living Room") == "living"
    assert normalize_room_type("dining room") == "dining"
    assert normalize_room_type("prayer_room") == "pooja"
