import sys
import os

# Add the current directory to path
sys.path.append(os.getcwd())

import logging
logging.basicConfig(level=logging.INFO)

from services.constraint_solver import solve_layout

def test_solver():
    plot_width = 30.0
    plot_height = 50.0
    
    rooms = [
        {'id': 'foyer_1', 'normalized_type': 'foyer', 'type': 'foyer'},
        {'id': 'liv_1', 'normalized_type': 'living', 'type': 'living'},
        {'id': 'din_1', 'normalized_type': 'dining', 'type': 'dining'},
        {'id': 'kit_1', 'normalized_type': 'kitchen', 'type': 'kitchen'},
        {'id': 'bath_1', 'normalized_type': 'bathroom', 'type': 'bathroom'},
        {'id': 'park_1', 'normalized_type': 'car_parking', 'type': 'car_parking'}
    ]
    
    try:
        print("Testing constraint solver WITH strict_topology...")
        res = solve_layout(
            plot_width_ft=plot_width, 
            plot_height_ft=plot_height, 
            rooms=rooms,
            entry_direction='S',
            max_time_seconds=5.0
        )
        print("Status:", res['status'])
        for r in res.get('rooms', []):
            print(f"{r['normalized_type']}: y={r['y']} to {r['y']+r['height']} (cx={r['x']+r['width']/2}, cy={r['y']+r['height']/2})")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_solver()
