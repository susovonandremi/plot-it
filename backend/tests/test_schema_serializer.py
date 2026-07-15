# backend/tests/test_schema_serializer.py
import pytest
from services.schema_serializer import serialize_floor_plan

def test_schema_serializer_output():
    # Mock rooms
    placed_rooms = [
        {'id': 'bed_1', 'type': 'bedroom', 'x': 5.0, 'y': 5.0, 'width': 12.0, 'height': 12.0, 'zone': 'SW'},
        {'id': 'bath_1', 'type': 'bathroom', 'x': 17.0, 'y': 5.0, 'width': 8.0, 'height': 6.0, 'zone': 'W'},
        {'id': 'passage_1', 'type': 'passage', 'x': 17.0, 'y': 11.0, 'width': 8.0, 'height': 6.0, 'zone': 'W'},
    ]
    
    vastu_score = {'overall': 85, 'score': 85, 'label': 'Good', 'color': 'green'}
    
    schema = serialize_floor_plan(
        placed_rooms=placed_rooms,
        plot_width=30.0,
        plot_height=30.0,
        vastu_score=vastu_score,
        floor_number=0,
        solver_time_ms=120
    )
    
    # Assert top-level keys
    assert schema['version'] == '1.0.0'
    assert 'metadata' in schema
    assert 'rooms' in schema
    assert 'walls' in schema
    assert 'doors' in schema
    assert 'windows' in schema
    assert 'fixtures' in schema
    assert 'structural' in schema
    assert 'site_context' in schema
    assert 'dimension_chains' in schema
    
    # Assert metadata validation
    metadata = schema['metadata']
    assert metadata['plot_width_ft'] == 30.0
    assert metadata['plot_height_ft'] == 30.0
    assert metadata['plot_area_sqft'] == 900.0
    assert metadata['vastu_score']['overall'] == 85
    assert metadata['floor_label'] == "GROUND FLOOR PLAN"
    
    # Assert rooms are shifted correctly
    rooms = schema['rooms']
    assert len(rooms) == 3
    # Minimum coordinate of rooms was (5,5), so shifted coordinates should start at 0
    assert rooms[0]['x'] == 0.0
    assert rooms[0]['y'] == 0.0
    assert rooms[0]['width'] == 12.0
    assert rooms[0]['height'] == 12.0
    
    # Assert fixtures are auto-generated
    fixtures = schema['fixtures']
    assert len(fixtures) == 2  # WC and Basin for the bathroom
    assert fixtures[0]['type'] == 'toilet'
    assert fixtures[1]['type'] == 'washbasin'
    
    # Assert dimension chains
    dims = schema['dimension_chains']
    assert dims['overall_width']['value_ft'] == 30.0
    assert dims['overall_depth']['value_ft'] == 30.0
