
import asyncio
from services.building_program import BuildingProgram, BuildingType
from services.constraint_solver import ConstraintSolver

def test_solver():
    print("Testing strict topology solver...")
    
    # ... previous setup ...
    rooms = [
        {'id': 'foyer_1', 'type': 'FOYER', 'normalized_type': 'foyer', 'width': 6, 'height': 8, 'min_area': 48},
        {'id': 'living_1', 'type': 'LIVING ROOM', 'normalized_type': 'living', 'width': 12, 'height': 14, 'min_area': 168},
        {'id': 'dining_1', 'type': 'DINING', 'normalized_type': 'dining', 'width': 10, 'height': 10, 'min_area': 100},
        {'id': 'kitchen_1', 'type': 'KITCHEN', 'normalized_type': 'kitchen', 'width': 8, 'height': 10, 'min_area': 80},
    ]
    
    for r in rooms:
        r['min_w'] = r['width'] - 2
        r['max_w'] = r['width'] + 2
        r['min_h'] = r['height'] - 2
        r['max_h'] = r['height'] + 2
    
    plot_w, plot_h = 30.0, 50.0
    solver = ConstraintSolver(plot_width_ft=plot_w, plot_height_ft=plot_h)
    
    # We call solve
    try:
        result = solver.solve(
            expanded=rooms,
            vastu_assignments={},
            entry_direction='N',
            fixed_positions={},
            relax_aspect=3.0,
            use_adjacency=True,
            use_vastu=False
        )
        if result['status'] == 'OPTIMAL' or result['status'] == 'FEASIBLE':
            print("SUCCESS: Layout generated!")
            for item in result['placement']:
                print(f" - {item['id']}: x={item['x']}, y={item['y']}, w={item['width']}, h={item['height']}")
        else:
            print(f"FAILED: Solver returned {result['status']}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_solver()
