
import pytest
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.vastu_engine import assign_vastu_zones, calculate_vastu_score
from services.layout_engine import generate_layout
from services.svg_renderer import render_blueprint

def test_full_pipeline_end_to_end():
    # 1. Setup Input Data (simulating parser output)
    plot_size = 1500
    rooms = [
        {"id": "k1", "type": "Kitchen"},
        {"id": "m1", "type": "Master Bedroom"},
        {"id": "l1", "type": "Living Room"},
        {"id": "b1", "type": "Bathroom"},
        {"id": "b2", "type": "Bedroom"}
    ]
    
    # 2. Vastu Engine
    assigned_zones = assign_vastu_zones(rooms)
    vastu_results = calculate_vastu_score(assigned_zones)
    
    assert vastu_results['score'] > 0
    assert 'label' in vastu_results
    assert 'color' in vastu_results
    
    # Evaluate assigned zones explicitly using ID
    assert assigned_zones['k1'] in ['SE', 'NW'] 
    assert assigned_zones['m1'] == 'SW'

    # Inject zones into rooms format for LayoutEngine compat
    for r in rooms:
        r['zone'] = assigned_zones.get(r['id'], 'C')

    # 3. Layout Engine
    layout_results = generate_layout(plot_size, rooms, floors=1)
    
    assert 'rooms' in layout_results
    assert 'total_area_used' in layout_results
    assert 'plot_dimensions' in layout_results
    
    # Check if rooms have coordinates and dimensions
    for room in layout_results['rooms']:
        assert 'x' in room
        assert 'y' in room
        assert 'width' in room
        assert 'height' in room
        assert room['width'] > 0
        assert room['height'] > 0

    # 4. SVG Renderer (Free Tier)
    svg_free = render_blueprint(
        layout_results['rooms'], 
        layout_results['plot_dimensions'][0], 
        layout_results['plot_dimensions'][1], 
        vastu_results, 
        user_tier="free"
    )
    
    # Check for SVG structure
    assert svg_free.startswith('<svg') or svg_free.startswith('<?xml')
    # Check for updated text watermark implementation
    assert 'PlotAI.com' in svg_free
    # 5. SVG Renderer (Paid Tier)
    svg_paid = render_blueprint(
        layout_results['rooms'], 
        layout_results['plot_dimensions'][0], 
        layout_results['plot_dimensions'][1], 
        vastu_results, 
        user_tier="pro"
    )
    
    # Check for clean vector output
    assert "<rect" in svg_paid
    # Should NOT have the watermark
    assert "PlotAI.com" not in svg_paid

if __name__ == "__main__":
    pytest.main([__file__])
