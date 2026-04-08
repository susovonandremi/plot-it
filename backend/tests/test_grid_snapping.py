"""
Test grid snapping: verifies all room coordinates are integers.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.layout_engine import generate_layout, snap_to_grid, snap_room_to_grid

def main():
    # Test snap_to_grid
    print("=== snap_to_grid() tests ===")
    assert snap_to_grid(12.3) == 12.0, f"Expected 12.0, got {snap_to_grid(12.3)}"
    assert snap_to_grid(12.7) == 13.0, f"Expected 13.0, got {snap_to_grid(12.7)}"
    assert snap_to_grid(5.5) == 6.0, f"Expected 6.0, got {snap_to_grid(5.5)}"
    assert snap_to_grid(0.0) == 0.0
    print("  snap_to_grid(12.3) =", snap_to_grid(12.3))
    print("  snap_to_grid(12.7) =", snap_to_grid(12.7))
    print("  snap_to_grid(5.5)  =", snap_to_grid(5.5))
    print("  All snap_to_grid tests PASSED")
    print()

    # Test snap_room_to_grid
    print("=== snap_room_to_grid() test ===")
    test_room = {'id': 'test', 'type': 'BEDROOM', 'x': 12.3, 'y': 5.7, 'width': 14.4, 'height': 10.6, 'zone': 'SW'}
    snapped = snap_room_to_grid(test_room)
    print(f"  Before: x={test_room['x']}, y={test_room['y']}, w={test_room['width']}, h={test_room['height']}")
    print(f"  After:  x={snapped['x']}, y={snapped['y']}, w={snapped['width']}, h={snapped['height']}")
    assert snapped['x'] == 12.0
    assert snapped['y'] == 6.0
    assert snapped['width'] == 14.0
    assert snapped['height'] == 11.0
    assert snapped['zone'] == 'SW'  # Preserved extra keys
    print("  snap_room_to_grid test PASSED")
    print()

    # Full pipeline test: "2000 sqft, 3 bed, 2 bath, kitchen, dining, living"
    print("=== Full Pipeline Test ===")
    rooms = [
        {"type": "bedroom", "count": 3},
        {"type": "bathroom", "count": 2},
        {"type": "kitchen", "count": 1},
        {"type": "dining", "count": 1},
        {"type": "living", "count": 1}
    ]

    layout = generate_layout(2000, rooms)

    print(f"  Total rooms: {len(layout['rooms'])}")
    print(f"  Plot dimensions: {layout['plot_dimensions']}")
    print()
    print("  Room Coordinates:")
    print("  " + "-" * 60)

    all_integer = True
    for room in layout['rooms']:
        x = room['x']
        y = room['y']
        w = room['width']
        h = room['height']
        is_int = all(v == int(v) for v in [x, y, w, h])
        if not is_int:
            all_integer = False
        status = "OK" if is_int else "FAIL"
        print(f"  {room['id']:20s}  x={int(x):3d}  y={int(y):3d}  width={int(w):3d}  height={int(h):3d}  [{status}]")

    print("  " + "-" * 60)
    if all_integer:
        print("  RESULT: ALL coordinates are integers - GRID SNAPPING WORKS!")
    else:
        print("  RESULT: FAILED - Some coordinates have decimals!")

    assert all_integer, "Grid snapping failed - some coordinates are not integers!"

if __name__ == "__main__":
    main()
