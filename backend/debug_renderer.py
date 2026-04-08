
import sys
import os

# Add the current directory to path
sys.path.append(os.getcwd())

import json
from services.professional_svg_renderer import render_blueprint_professional
from services.building_program import BuildingProgram, BuildingType

def test_renderer():
    # Mock data based on a successful generation
    plot_width = 30.0
    plot_height = 50.0
    floor_number = 0
    
    # Minimal placement data
    placement_data = [
        {'id': 'liverm', 'type': 'LIVING', 'x': 5, 'y': 5, 'width': 12, 'height': 15, 'label': 'LIVING'},
        {'id': 'kit01', 'type': 'KITCHEN', 'x': 20, 'y': 5, 'width': 8, 'height': 10, 'label': 'KITCHEN'}
    ]
    
    # Mock building program
    program = BuildingProgram(
        plot_area=1500,
        user_rooms=[],
        building_type=BuildingType.INDEPENDENT_HOUSE,
        floors_total=2
    )

    try:
        print("Starting manual rendering test...")
        svg = render_blueprint_professional(
            placement_data=placement_data,
            plot_width=plot_width,
            plot_height=plot_height,
            vastu_score={'total_score': 80},
            floor_number=floor_number,
            building_program=program
        )
        if svg:
            print(f"SUCCESS: SVG generated (length: {len(svg)})")
            with open(r'C:\Users\susov\.gemini\antigravity\brain\206b2e83-0dcc-4a39-a565-a92cf9923f1c\debug_output.svg', 'w', encoding='utf-8') as f:
                f.write(svg)
            print("Saved to debug_output.svg")
        else:
            print("FAILURE: SVG is empty string")
    except Exception as e:
        import traceback
        print("CRASH DETECTED:")
        traceback.print_exc()

if __name__ == "__main__":
    test_renderer()
