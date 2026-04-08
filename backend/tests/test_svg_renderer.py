
import pytest
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.svg_renderer import render_blueprint

def test_svg_structure():
    # Mock data
    rooms = [{"id": "bedroom_1", "type": "Bedroom", "x": 10, "y": 10, "width": 10, "height": 10}]
    vastu = {"score": 100, "label": "Excellent", "color": "green", "violations": []}
    
    svg = render_blueprint(rooms, 40, 60, vastu, user_tier="pro")
    
    assert "<svg" in svg
    assert "width=\"500px\"" in svg # 40*10 + 100 margin
    assert "height=\"700px\"" in svg # 60*10 + 100 margin
    assert "Bedroom" in svg
    assert "Vastu: 100%" in svg

def test_watermark_free_tier():
    rooms = [{"id": "bedroom_1", "type": "Bedroom", "x": 10, "y": 10, "width": 10, "height": 10}]
    vastu = {"score": 100, "label": "Excellent", "color": "green", "violations": []}
    
    svg = render_blueprint(rooms, 40, 60, vastu, user_tier="free")
    
    # Should contain base64 image data OR the vector fallback text
    assert "data:image/png;base64," in svg or "PlotAI.com" in svg

def test_clean_output_paid_tier():
    rooms = [{"id": "bedroom_1", "type": "Bedroom", "x": 10, "y": 10, "width": 10, "height": 10}]
    vastu = {"score": 100, "label": "Excellent", "color": "green", "violations": []}
    
    svg = render_blueprint(rooms, 40, 60, vastu, user_tier="pro")
    
    # Should NOT contain base64 image data
    assert "data:image/png;base64," not in svg
    # Should check for vector rects
    assert "<rect" in svg
