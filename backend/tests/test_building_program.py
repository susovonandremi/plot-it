"""
Tests for BuildingProgram service.
Tests door rules, window budgets, mandatory element injection,
and building type context awareness.
"""

import pytest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.building_program import (
    BuildingProgram, BuildingType, create_building_program,
    DOOR_ALLOWED_PAIRS, NO_DOOR_PAIRS, WINDOW_BUDGET,
)


# ═══════════════════════════════════════════════════════════════════════
# DOOR RULES
# ═══════════════════════════════════════════════════════════════════════

class TestDoorRules:
    """Tests for smart door placement logic."""
    
    @pytest.fixture
    def program(self):
        return BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.INDEPENDENT_HOUSE,
            user_rooms=[
                {'type': 'Bedroom', 'count': 3},
                {'type': 'Bathroom', 'count': 2},
                {'type': 'Kitchen', 'count': 1},
                {'type': 'Living Room', 'count': 1},
                {'type': 'Dining Room', 'count': 1},
            ]
        )
    
    def test_bedroom_to_passage_gets_door(self, program):
        """Bedroom opens to passage — standard internal door."""
        result = program.should_place_door('bedroom', 'passage')
        assert result is not None
        assert result['type'] == 'internal'
        assert result['width'] == 3.0
    
    def test_bedroom_to_bathroom_gets_door(self, program):
        """Attached bathroom door — narrower internal door."""
        result = program.should_place_door('bedroom', 'bathroom')
        assert result is not None
        assert result['type'] == 'internal'
        assert result['width'] == 2.5
    
    def test_kitchen_to_dining_gets_door(self, program):
        """Kitchen opens to dining — internal door."""
        result = program.should_place_door('kitchen', 'dining')
        assert result is not None
        assert result['type'] == 'internal'
    
    def test_living_to_passage_gets_arch(self, program):
        """Living room opens to passage — open arch (wider)."""
        result = program.should_place_door('living', 'passage')
        assert result is not None
        assert result['type'] == 'open_arch'
        assert result['width'] == 4.0
    
    def test_entry_to_living_gets_main_door(self, program):
        """Entry → living = main door (widest)."""
        result = program.should_place_door('entry', 'living')
        assert result is not None
        assert result['type'] == 'main_door'
        assert result['width'] == 3.5
    
    def test_bedroom_to_bedroom_no_door(self, program):
        """Two bedrooms sharing a wall = NO door."""
        result = program.should_place_door('bedroom', 'bedroom')
        assert result is None
    
    def test_bathroom_to_kitchen_no_door(self, program):
        """Bathroom ↔ kitchen = NO door (hygiene)."""
        result = program.should_place_door('bathroom', 'kitchen')
        assert result is None
    
    def test_bathroom_to_living_no_door(self, program):
        """Bathroom ↔ living = NO door."""
        result = program.should_place_door('bathroom', 'living')
        assert result is None
    
    def test_kitchen_to_bedroom_no_door(self, program):
        """Kitchen ↔ bedroom = NO door (fumes)."""
        result = program.should_place_door('kitchen', 'bedroom')
        assert result is None
    
    def test_staircase_to_bedroom_no_door(self, program):
        """Staircase ↔ bedroom = NO door."""
        result = program.should_place_door('staircase', 'bedroom')
        assert result is None
    
    def test_unlisted_pairs_no_door(self, program):
        """Pairs not in allowed list = no door by default."""
        result = program.should_place_door('garage', 'pooja')
        assert result is None
    
    def test_type_normalization(self, program):
        """Room type aliases are normalized correctly."""
        # "Living Room" → "living", "Bed Room" → "bedroom"
        result = program.should_place_door('Living Room', 'Passage')
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# WINDOW BUDGET
# ═══════════════════════════════════════════════════════════════════════

class TestWindowBudget:
    """Tests for smart window allocation."""
    
    @pytest.fixture
    def program(self):
        return BuildingProgram(plot_area=2000)
    
    def test_bedroom_gets_one_window(self, program):
        budget = program.get_window_budget('bedroom')
        assert budget['count'] == 1
        assert budget['width'] == 4.0
        assert budget['type'] == 'standard'
    
    def test_master_bedroom_gets_two_windows(self, program):
        budget = program.get_window_budget('master_bedroom')
        assert budget['count'] == 2
    
    def test_living_gets_two_large_windows(self, program):
        budget = program.get_window_budget('living')
        assert budget['count'] == 2
        assert budget['type'] == 'large'
        assert budget['width'] == 5.0
    
    def test_bathroom_gets_ventilator(self, program):
        budget = program.get_window_budget('bathroom')
        assert budget['count'] == 1
        assert budget['type'] == 'ventilator'
        assert budget['width'] == 1.5
    
    def test_passage_gets_no_windows(self, program):
        budget = program.get_window_budget('passage')
        assert budget['count'] == 0
    
    def test_staircase_gets_no_windows(self, program):
        budget = program.get_window_budget('staircase')
        assert budget['count'] == 0
    
    def test_kitchen_gets_one_window(self, program):
        budget = program.get_window_budget('kitchen')
        assert budget['count'] == 1
    
    def test_total_window_count_reasonable(self, program):
        """For a typical 3BHK, total windows should be 6-10."""
        room_types = ['master_bedroom', 'bedroom', 'bedroom', 'living',
                      'dining', 'kitchen', 'bathroom', 'bathroom']
        total = sum(program.get_window_budget(t)['count'] for t in room_types)
        assert 6 <= total <= 12, f"Got {total} windows — should be 6-12"


# ═══════════════════════════════════════════════════════════════════════
# MANDATORY ELEMENTS
# ═══════════════════════════════════════════════════════════════════════

class TestMandatoryElements:
    """Tests for auto-injection of required architectural elements."""
    
    def test_house_ground_floor_gets_passage(self):
        program = BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.INDEPENDENT_HOUSE,
            floor_number=0,
            user_rooms=[{'type': 'Bedroom', 'count': 3}]
        )
        rooms = program.get_enriched_rooms()
        passage_rooms = [r for r in rooms if r['type'].lower() == 'passage']
        assert len(passage_rooms) >= 1, "Ground floor should have a passage"
    
    def test_multi_floor_house_gets_staircase(self):
        program = BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.INDEPENDENT_HOUSE,
            floor_number=1,
            floors_total=2,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        stair_rooms = [r for r in rooms if r['type'].lower() == 'staircase']
        assert len(stair_rooms) >= 1, "Multi-floor should have staircase"
    
    def test_single_floor_no_staircase(self):
        program = BuildingProgram(
            plot_area=1500,
            building_type=BuildingType.INDEPENDENT_HOUSE,
            floor_number=0,
            floors_total=1,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        stair_rooms = [r for r in rooms if r['type'].lower() == 'staircase']
        assert len(stair_rooms) == 0, "Single floor should NOT have staircase"
    
    def test_lift_injected_when_requested(self):
        program = BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.APARTMENT,
            has_lift=True,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        lift_rooms = [r for r in rooms if r['type'].lower() == 'lift']
        assert len(lift_rooms) >= 1
    
    def test_no_lift_by_default(self):
        program = BuildingProgram(
            plot_area=2000,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        lift_rooms = [r for r in rooms if r['type'].lower() == 'lift']
        assert len(lift_rooms) == 0
    
    def test_verandah_injected_when_requested(self):
        program = BuildingProgram(
            plot_area=2000,
            has_verandah=True,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        verandah_rooms = [r for r in rooms if r['type'].lower() == 'verandah']
        assert len(verandah_rooms) >= 1
    
    def test_no_duplicate_mandatory_elements(self):
        """If user already specified a passage, don't add another."""
        program = BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.INDEPENDENT_HOUSE,
            user_rooms=[
                {'type': 'Bedroom', 'count': 2},
                {'type': 'Passage', 'count': 1},  # User-specified
            ]
        )
        rooms = program.get_enriched_rooms()
        passage_rooms = [r for r in rooms if r['type'].lower() == 'passage']
        assert len(passage_rooms) == 1, "Should not duplicate user-specified passage"


# ═══════════════════════════════════════════════════════════════════════
# BUILDING CONTEXT
# ═══════════════════════════════════════════════════════════════════════

class TestBuildingContext:
    """Tests for building type awareness and metadata."""
    
    def test_floor_label_ground(self):
        program = BuildingProgram(plot_area=1000, floor_number=0)
        assert program.get_floor_label() == "GROUND FLOOR PLAN"
    
    def test_floor_label_1st(self):
        program = BuildingProgram(plot_area=1000, floor_number=1, floors_total=3)
        assert program.get_floor_label() == "1ST FLOOR PLAN"
    
    def test_floor_label_2nd(self):
        program = BuildingProgram(plot_area=1000, floor_number=2, floors_total=3)
        assert program.get_floor_label() == "2ND FLOOR PLAN"
    
    def test_floor_label_3rd(self):
        program = BuildingProgram(plot_area=1000, floor_number=3, floors_total=4)
        assert program.get_floor_label() == "3RD FLOOR PLAN"
    
    def test_floor_label_5th(self):
        program = BuildingProgram(plot_area=1000, floor_number=5, floors_total=6)
        assert program.get_floor_label() == "5TH FLOOR PLAN"
    
    def test_entry_wall_side_east(self):
        program = BuildingProgram(plot_area=1000, entry_direction='E')
        assert program.get_entry_wall_side() == 'right'
    
    def test_entry_wall_side_north(self):
        program = BuildingProgram(plot_area=1000, entry_direction='N')
        assert program.get_entry_wall_side() == 'top'
    
    def test_metadata_populated(self):
        program = BuildingProgram(
            plot_area=2000,
            building_type=BuildingType.APARTMENT,
            floor_number=3,
            floors_total=5,
            entry_direction='E',
            has_lift=True,
            user_rooms=[{'type': 'Bedroom', 'count': 2}]
        )
        rooms = program.get_enriched_rooms()
        meta = program.get_metadata()
        
        assert meta['building_type'] == BuildingType.APARTMENT
        assert meta['floor_number'] == 3
        assert meta['floor_label'] == '3RD FLOOR PLAN'
        assert meta['entry_direction'] == 'E'
        assert meta['has_passage'] is True
        assert meta['has_lift'] is True
    
    def test_is_multi_floor(self):
        p1 = BuildingProgram(plot_area=1000, floors_total=1)
        assert p1.is_multi_floor is False
        
        p2 = BuildingProgram(plot_area=1000, floors_total=3)
        assert p2.is_multi_floor is True
    
    def test_factory_function(self):
        p = create_building_program(
            plot_area=2000,
            user_rooms=[{'type': 'Bedroom', 'count': 3}],
            building_type='apartment',
            floor_number=2,
            floors_total=4,
            entry_direction='S',
            has_lift=True
        )
        assert isinstance(p, BuildingProgram)
        assert p.building_type == 'apartment'
        rooms = p.get_enriched_rooms()
        assert len(rooms) > 1


# ═══════════════════════════════════════════════════════════════════════
# VILLA TYPE
# ═══════════════════════════════════════════════════════════════════════

class TestVillaProgram:
    """Tests for villa building type specifics."""
    
    def test_villa_ground_floor_gets_foyer(self):
        program = BuildingProgram(
            plot_area=3000,
            building_type=BuildingType.VILLA,
            floor_number=0,
            user_rooms=[{'type': 'Bedroom', 'count': 4}]
        )
        rooms = program.get_enriched_rooms()
        foyer_rooms = [r for r in rooms if r['type'].lower() == 'foyer']
        assert len(foyer_rooms) >= 1, "Villa ground floor should have a foyer"
    
    def test_villa_upper_floor_gets_staircase(self):
        program = BuildingProgram(
            plot_area=3000,
            building_type=BuildingType.VILLA,
            floor_number=1,
            floors_total=2,
            user_rooms=[{'type': 'Bedroom', 'count': 3}]
        )
        rooms = program.get_enriched_rooms()
        stair_rooms = [r for r in rooms if r['type'].lower() == 'staircase']
        assert len(stair_rooms) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
