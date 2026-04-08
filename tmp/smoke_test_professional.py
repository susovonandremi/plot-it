import sys
import os
import logging

# Setup paths
workspace_root = r"e:\Project\plot-ai"
backend_path = os.path.join(workspace_root, "backend")
sys.path.append(backend_path)

from services.professional_svg_renderer import render_blueprint_professional

# Mock data
placement_data = [
    {"type": "Living", "x": 0, "y": 0, "width": 15, "height": 20, "id": "room1"},
    {"type": "Bedroom", "x": 15, "y": 0, "width": 12, "height": 12, "id": "room2"},
    {"type": "Staircase", "x": 15, "y": 12, "width": 12, "height": 8, "id": "stair1", "normalized_type": "staircase"}
]

try:
    print("Attempting to render blueprint...")
    svg = render_blueprint_professional(
        placement_data=placement_data,
        plot_width=30,
        plot_height=40,
        vastu_score=85,
        user_tier="free",
        original_unit_system={"system": "metric"},
        heavy_elements={},
        building_program=None,
        floor_number=0,
        shape_config={"type": "rectangle"}
    )
    print("SUCCESS: SVG generated length:", len(svg))
except Exception as e:
    import traceback
    print(f"FAILED with error: {e}")
    traceback.print_exc()
