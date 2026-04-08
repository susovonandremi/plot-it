import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.llm_spatial_reasoner import get_spatial_plan
from services.strip_layout_engine import generate_strip_layout

def test_vertical():
    plot_width = 20.0
    plot_depth = 50.0
    floors = 1
    entry_direction = "S"
    
    rooms = [
        {"id": "bedroom_1", "type": "Bedroom"},
        {"id": "master_bedroom_1", "type": "Master Bedroom"},
        {"id": "kitchen_1", "type": "Kitchen"},
        {"id": "living_room_1", "type": "Living Room"},
        {"id": "bathroom_1", "type": "Bathroom"},
        {"id": "bathroom_2", "type": "Bathroom"},
        {"id": "corridor", "type": "passage"}
    ]
    
    plan = get_spatial_plan("20x50ft narrow house", plot_width, plot_depth, floors, entry_direction, rooms)
    layout = generate_strip_layout(plot_width, plot_depth, plan, rooms, entry_direction)
    
    print(f"\n TESTING VERTICAL ORIENTATION ({plot_width} W x {plot_depth} D)")
    print("PLACED ROOMS:")
    for r in layout:
        print(f"  {str(r['id'])[:16]:16} [{r.get('corridor_orientation', '')}] -> X: {r['x']:<5.1f} Y: {r['y']:<5.1f} | W: {r['width']:<5.1f} H: {r['height']:<5.1f}")
        
    x_exceeded = any(r['x'] + r['width'] > plot_width + 0.1 for r in layout)
    y_exceeded = any(r['y'] + r['height'] > plot_depth + 0.1 for r in layout)
    
    if x_exceeded or y_exceeded:
        print(" FAILED: Bounds exceeded.")
        sys.exit(1)
        
    print(" SUCCESS: Vertical engine executes cleanly.")

if __name__ == "__main__":
    test_vertical()
