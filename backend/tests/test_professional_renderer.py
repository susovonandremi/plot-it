"""
Tests for Professional SVG Renderer
Validates wall segment extraction, merging, door/window placement, and wall breaks.
"""

import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.professional_svg_renderer import (
    extract_wall_segments,
    merge_collinear_walls,
    find_shared_wall,
    find_door_positions,
    find_window_positions,
    split_wall_at_opening,
    apply_openings_to_walls,
    render_blueprint_professional,
    _fmt_feet_inches,
)


# ═══════════════════════════════════════════════════════════
# Wall Segment Tests
# ═══════════════════════════════════════════════════════════

class TestWallSegments:
    def test_single_room_generates_4_walls(self):
        rooms = [{'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10}]
        segments = extract_wall_segments(rooms)
        assert len(segments['horizontal']) == 2  # top + bottom
        assert len(segments['vertical']) == 2    # left + right

    def test_shared_wall_merged(self):
        """Two adjacent rooms sharing a vertical wall → merged into one segment."""
        rooms = [
            {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
            {'id': 'r2', 'type': 'kitchen', 'x': 10, 'y': 0, 'width': 10, 'height': 10},
        ]
        segments = extract_wall_segments(rooms)
        
        # Without merging: 4+4 = 8 vertical walls
        # With merging: r1-right and r2-left are same line → 3 vertical walls
        # (r1-left, shared, r2-right)
        assert len(segments['vertical']) == 3, \
            f"Expected 3 vertical walls (shared merge), got {len(segments['vertical'])}"

    def test_three_rooms_horizontal_strip(self):
        """Three rooms in a row: should have 4 vertical walls (not 6)."""
        rooms = [
            {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
            {'id': 'r2', 'type': 'kitchen', 'x': 10, 'y': 0, 'width': 10, 'height': 10},
            {'id': 'r3', 'type': 'living', 'x': 20, 'y': 0, 'width': 10, 'height': 10},
        ]
        segments = extract_wall_segments(rooms)
        assert len(segments['vertical']) == 4  # left, shared1, shared2, right

    def test_exterior_walls_identified(self):
        """Walls on the plot boundary should be marked as exterior."""
        rooms = [
            {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10},
            {'id': 'r2', 'type': 'kitchen', 'x': 10, 'y': 0, 'width': 10, 'height': 10},
        ]
        bounds = {'min_x': 0, 'min_y': 0, 'max_x': 20, 'max_y': 10}
        segments = extract_wall_segments(rooms, bounds)
        
        # All horizontal walls should be exterior (y=0, y=10)
        for wall in segments['horizontal']:
            assert wall['is_exterior'] is True
        
        # Left (x=0) and right (x=20) vertical walls are exterior
        # Shared wall at x=10 is interior
        ext_v = [w for w in segments['vertical'] if w['is_exterior']]
        int_v = [w for w in segments['vertical'] if not w['is_exterior']]
        assert len(ext_v) == 2, f"Expected 2 exterior vertical walls, got {len(ext_v)}"
        assert len(int_v) == 1, f"Expected 1 interior vertical wall, got {len(int_v)}"


class TestMergeCollinear:
    def test_merge_identical_walls(self):
        """Two walls on same line with same span → one wall."""
        walls = [
            {'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0, 'room_ids': ['a']},
            {'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0, 'room_ids': ['b']},
        ]
        result = merge_collinear_walls(walls, 'horizontal')
        assert len(result) == 1
        assert set(result[0]['room_ids']) == {'a', 'b'}

    def test_merge_adjacent_walls(self):
        """Two walls on same line, end-to-end → one continuous wall."""
        walls = [
            {'x1': 0, 'y1': 5, 'x2': 10, 'y2': 5, 'room_ids': ['a']},
            {'x1': 10, 'y1': 5, 'x2': 20, 'y2': 5, 'room_ids': ['b']},
        ]
        result = merge_collinear_walls(walls, 'horizontal')
        assert len(result) == 1
        assert result[0]['x1'] == 0
        assert result[0]['x2'] == 20

    def test_no_merge_different_lines(self):
        """Walls on different Y values should NOT merge."""
        walls = [
            {'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0, 'room_ids': ['a']},
            {'x1': 0, 'y1': 5, 'x2': 10, 'y2': 5, 'room_ids': ['b']},
        ]
        result = merge_collinear_walls(walls, 'horizontal')
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════
# Door / Window Tests
# ═══════════════════════════════════════════════════════════

class TestDoors:
    def test_find_shared_wall_vertical(self):
        room1 = {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10}
        room2 = {'id': 'r2', 'type': 'kitchen', 'x': 10, 'y': 0, 'width': 10, 'height': 10}
        
        shared = find_shared_wall(room1, room2)
        assert shared is not None
        assert shared['orientation'] == 'vertical'
        assert abs(shared['x1'] - 10) < 0.1

    def test_find_shared_wall_horizontal(self):
        room1 = {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 8}
        room2 = {'id': 'r2', 'type': 'living', 'x': 0, 'y': 8, 'width': 10, 'height': 10}
        
        shared = find_shared_wall(room1, room2)
        assert shared is not None
        assert shared['orientation'] == 'horizontal'
        assert abs(shared['y1'] - 8) < 0.1

    def test_no_shared_wall_for_distant_rooms(self):
        room1 = {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 10, 'height': 10}
        room2 = {'id': 'r2', 'type': 'kitchen', 'x': 20, 'y': 0, 'width': 10, 'height': 10}
        
        shared = find_shared_wall(room1, room2)
        assert shared is None

    def test_door_placed_between_adjacent_rooms(self):
        rooms = [
            {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 12, 'height': 10},
            {'id': 'r2', 'type': 'living', 'x': 12, 'y': 0, 'width': 12, 'height': 10},
        ]
        doors = find_door_positions(rooms)
        assert len(doors) == 1
        assert doors[0]['orientation'] == 'vertical'

    def test_no_door_between_bathroom_and_kitchen(self):
        rooms = [
            {'id': 'k1', 'type': 'kitchen', 'x': 0, 'y': 0, 'width': 12, 'height': 10},
            {'id': 'b1', 'type': 'bathroom', 'x': 12, 'y': 0, 'width': 8, 'height': 10},
        ]
        doors = find_door_positions(rooms)
        assert len(doors) == 0, "Should not place door between kitchen and bathroom"

    def test_window_on_exterior_wall(self):
        rooms = [
            {'id': 'r1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 12, 'height': 10},
        ]
        bounds = {'min_x': 0, 'min_y': 0, 'max_x': 30, 'max_y': 20}
        windows = find_window_positions(rooms, bounds)
        
        # Bedroom has left wall (x=0) and top wall (y=0) on boundary
        assert len(windows) >= 2, f"Expected at least 2 windows, got {len(windows)}"

    def test_no_window_on_bathroom(self):
        rooms = [
            {'id': 'b1', 'type': 'bathroom', 'x': 0, 'y': 0, 'width': 8, 'height': 8},
        ]
        bounds = {'min_x': 0, 'min_y': 0, 'max_x': 8, 'max_y': 8}
        windows = find_window_positions(rooms, bounds)
        assert len(windows) == 0, "Bathrooms should not get windows"


class TestWallBreaks:
    def test_split_horizontal_wall(self):
        wall = {'x1': 0, 'y1': 10, 'x2': 20, 'y2': 10, 'room_ids': ['r1']}
        result = split_wall_at_opening(wall, opening_pos=10, opening_width=3, axis='horizontal')
        
        assert len(result) == 2, "Should split into two segments"
        assert result[0]['x2'] == 8.5  # 10 - 1.5
        assert result[1]['x1'] == 11.5  # 10 + 1.5

    def test_split_vertical_wall(self):
        wall = {'x1': 10, 'y1': 0, 'x2': 10, 'y2': 20, 'room_ids': ['r1']}
        result = split_wall_at_opening(wall, opening_pos=10, opening_width=3, axis='vertical')
        
        assert len(result) == 2
        assert result[0]['y2'] == 8.5
        assert result[1]['y1'] == 11.5


# ═══════════════════════════════════════════════════════════
# Formatting Tests
# ═══════════════════════════════════════════════════════════

class TestFormatting:
    def test_feet_inches_whole(self):
        assert _fmt_feet_inches(10.0) == "10'-0\""

    def test_feet_inches_half(self):
        assert _fmt_feet_inches(10.5) == "10'-6\""

    def test_feet_inches_fraction(self):
        result = _fmt_feet_inches(11.583)
        assert result == "11'-7\""  # 0.583 * 12 ≈ 7


# ═══════════════════════════════════════════════════════════
# Full Render Test
# ═══════════════════════════════════════════════════════════

class TestFullRender:
    def test_render_produces_valid_svg(self):
        rooms = [
            {'id': 'bed_1', 'type': 'bedroom', 'x': 0, 'y': 0, 'width': 12, 'height': 10,
             'area': 120, 'zone': 'SW'},
            {'id': 'kit_1', 'type': 'kitchen', 'x': 12, 'y': 0, 'width': 10, 'height': 10,
             'area': 100, 'zone': 'SE'},
            {'id': 'liv_1', 'type': 'living', 'x': 0, 'y': 10, 'width': 22, 'height': 10,
             'area': 220, 'zone': 'N'},
        ]
        vastu = {'score': 85, 'label': 'Good Vastu', 'color': 'green'}
        
        svg = render_blueprint_professional(rooms, 22, 20, vastu)
        
        assert svg.startswith('<svg')
        assert 'BEDROOM' in svg
        assert 'KITCHEN' in svg
        assert 'LIVING' in svg
        assert 'Vastu' in svg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
