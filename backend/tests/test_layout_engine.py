
import pytest
import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.layout_engine import generate_layout, has_overlap, place_rooms_on_grid, LayoutEngine, calculate_room_sizes
from services.vastu_engine import assign_vastu_zones

def test_staircase_placement_multi_floor():
    # 2 Floors -> Should include staircase
    rooms = [{"id": "l1", "type": "Living Room", "zone": "N"}]
    layout = generate_layout(1200, rooms, floors=2)
    
    assert layout['staircase'] is not None
    assert layout['staircase']['width'] > 0
    assert layout['staircase']['height'] > 0

def test_room_sizing_weights():
    rooms = [
        {"id": "mb1", "type": "Master Bedroom", "zone": "SW"},
        {"id": "k1", "type": "Kitchen", "zone": "SE"}
    ]
    layout = generate_layout(1000, rooms, floors=1)
    
    # IDs generated are normally type_N, but since we passed IDs mb1 and k1, engine should keep them
    mb = next(r for r in layout['rooms'] if r['id'] == "mb1")
    kitchen = next(r for r in layout['rooms'] if r['id'] == "k1")
    
    mb_area = mb['width'] * mb['height']
    k_area = kitchen['width'] * kitchen['height']
    
    assert mb_area > k_area

def test_overlap_detection():
    """Tests that has_overlap() correctly identifies overlapping rooms."""
    from services.layout_engine import has_overlap
    
    # Test case 1: Clear overlap
    room1 = {'x': 0, 'y': 0, 'width': 10, 'height': 10}
    room2 = {'x': 5, 'y': 5, 'width': 10, 'height': 10}
    assert has_overlap(room1, room2) == True, "Should detect overlap"
    
    # Test case 2: Edge touching (with margin, should be overlap)
    room3 = {'x': 10, 'y': 0, 'width': 10, 'height': 10}
    assert has_overlap(room1, room3) == True, "Should detect rooms too close (within margin)"
    
    # Test case 3: Proper separation (1ft gap + 1ft margin = 2ft total)
    room4 = {'x': 12, 'y': 0, 'width': 10, 'height': 10}
    assert has_overlap(room1, room4) == False, "Should NOT detect overlap (properly separated)"
    
    # Test case 4: Vertical separation
    room5 = {'x': 0, 'y': 12, 'width': 10, 'height': 10}
    assert has_overlap(room1, room5) == False, "Should NOT overlap vertically"

def test_no_overlaps_in_full_layout():
    """Integration test: Rooms should tile perfectly — no true geometric overlaps."""
    rooms = [
        {"type": "bedroom", "count": 3},
        {"type": "bathroom", "count": 2},
        {"type": "kitchen", "count": 1},
        {"type": "dining", "count": 1},
        {"type": "living", "count": 1}
    ]

    raw_assignments = assign_vastu_zones(rooms)
    sized = calculate_room_sizes(2000, rooms)
    placed = place_rooms_on_grid(60, 60, sized, raw_assignments)

    # In the treemap architecture rooms tile edge-to-edge (wall thickness
    # is handled by the structural engine's WallBoundaryGeometry).
    # Check for TRUE geometric overlap (non-zero intersection area).
    from shapely.geometry import box as shapely_box
    overlap_found = False
    for i, r1 in enumerate(placed):
        p1 = shapely_box(r1['x'], r1['y'], r1['x'] + r1['width'], r1['y'] + r1['height'])
        for r2 in placed[i+1:]:
            p2 = shapely_box(r2['x'], r2['y'], r2['x'] + r2['width'], r2['y'] + r2['height'])
            ix = p1.intersection(p2)
            if ix.area > 0.01:  # tolerance for floating-point rounding
                overlap_found = True
                break
        if overlap_found:
            break

    assert not overlap_found, "True geometric overlap detected in treemap layout!"

def test_treemap_coverage():
    """Test that the treemap produces 100% plot coverage (perfect tiling)."""
    rooms = [
        {"type": "bedroom", "count": 2},
        {"type": "living", "count": 1},
        {"type": "kitchen", "count": 1}
    ]
    layout = generate_layout(2000, rooms)

    total_room_area = sum(r.get('area', r['width'] * r['height']) for r in layout['rooms'])
    plot_area = layout['available_area']
    coverage = total_room_area / plot_area

    # Treemap should achieve near-perfect tiling (>99%)
    assert coverage > 0.99, f"Coverage too low: {coverage*100:.1f}%"

def test_logical_adjacency():
    """Verify Kitchen and Dining are placed as touching neighbours."""
    rooms = [
        {"type": "kitchen", "count": 1},
        {"type": "dining", "count": 1},
        {"type": "living", "count": 1}
    ]

    layout = generate_layout(2000, rooms)
    rooms_placed = layout['rooms']

    kitchen = next((r for r in rooms_placed if 'KITCHEN' in r['type']), None)
    dining = next((r for r in rooms_placed if 'DINING' in r['type']), None)

    assert kitchen and dining, "Kitchen or Dining missing"

    # In a treemap, neighbours share an edge.  Check that their bounding
    # boxes touch (intersection is a line/point, not an area).
    from shapely.geometry import box as shapely_box
    kp = shapely_box(kitchen['x'], kitchen['y'],
                     kitchen['x'] + kitchen['width'],
                     kitchen['y'] + kitchen['height'])
    dp = shapely_box(dining['x'], dining['y'],
                     dining['x'] + dining['width'],
                     dining['y'] + dining['height'])

    # They must at least touch (shared boundary)
    assert kp.touches(dp) or kp.intersects(dp), \
        "Kitchen and Dining should be adjacent in treemap"
