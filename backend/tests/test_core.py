import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.strip_layout_engine import generate_strip_layout, VERTICAL_CORE
from services.llm_spatial_reasoner import get_spatial_plan

def test_core():
    plot_width = 30.0
    plot_depth = 40.0
    
    rooms = [
        {"id": "bedroom_1", "type": "Bedroom"},
        {"id": "master_bedroom_1", "type": "Master Bedroom"},
        {"id": "kitchen_1", "type": "Kitchen"},
        {"id": "living_room_1", "type": "Living Room"},
        {"id": "bathroom_1", "type": "Bathroom"},
        {"id": "corridor", "type": "passage"},
        {"id": "staircase", "type": "Staircase"},
        {"id": "common_bath", "type": "Bathroom"}
    ]
    
    plan = get_spatial_plan("testing", plot_width, plot_depth, 1, "S", rooms)
    # inject common bath into service
    plan['service_zone'] = ["corridor", "staircase", "common_bath"]
    
    layout = generate_strip_layout(plot_width, plot_depth, plan, rooms, "S")
    
    for r in layout:
        if r['id'] in ['staircase', 'common_bath', 'corridor']:
            print(f"ROOM {r['id']:15} -> X: {r['x']:<5.1f} Y: {r['y']:<5.1f} | W: {r['width']:<5.1f}")
            
test_core()
