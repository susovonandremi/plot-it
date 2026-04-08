
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.svg_renderer import render_blueprint

def test_fallback_when_cairo_missing():
    """
    Test that the vector fallback is used when cairosvg raises an OSError or ImportError.
    We mock 'services.svg_renderer.apply_burn_in_watermark' to raise an Exception.
    """
    rooms = [{"id": "r1", "type": "Bedroom", "x": 10, "y": 10, "width": 10, "height": 10}]
    vastu = {"score": 100, "label": "Excellent", "color": "green"}
    
    # Mock apply_burn_in_watermark to fail
    with patch('services.svg_renderer.apply_burn_in_watermark', side_effect=OSError("dlopen failed")):
        svg = render_blueprint(rooms, 40, 60, vastu, user_tier="free")
        
        # Should catch OSError and fallback to vector watermark
        assert "PLOTAI.COM FREE" in svg
        assert "data:image/png;base64," not in svg

def test_fallback_when_import_fails():
    """
    Test fallback when cairosvg module is not installed (ImportError).
    """
    rooms = [{"id": "r1", "type": "Bedroom", "x": 10, "y": 10, "width": 10, "height": 10}]
    vastu = {"score": 100, "label": "Excellent", "color": "green"}
    
    with patch('services.svg_renderer.apply_burn_in_watermark', side_effect=ImportError("No module named cairosvg")):
        svg = render_blueprint(rooms, 40, 60, vastu, user_tier="free")
        
        assert "PLOTAI.COM FREE" in svg
