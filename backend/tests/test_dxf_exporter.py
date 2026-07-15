# backend/tests/test_dxf_exporter.py
from services.dxf_exporter import export_to_dxf
from services.schema_serializer import serialize_floor_plan

def test_dxf_export():
    placed_rooms = [
        {'id': 'bed_1', 'type': 'bedroom', 'x': 0.0, 'y': 0.0, 'width': 10.0, 'height': 12.0, 'zone': 'NW'},
        {'id': 'bath_1', 'type': 'bathroom', 'x': 10.0, 'y': 0.0, 'width': 5.0, 'height': 6.0, 'zone': 'W'},
    ]
    
    schema = serialize_floor_plan(
        placed_rooms=placed_rooms,
        plot_width=15.0,
        plot_height=12.0,
        vastu_score={'score': 90, 'overall': 90, 'label': 'Perfect', 'color': 'green'}
    )
    
    dxf_content = export_to_dxf(schema)
    
    # Assert headers and section markup
    assert dxf_content.startswith("0\nSECTION\n2\nENTITIES")
    assert dxf_content.endswith("0\nEOF\n")
    
    # Assert layer groups are present
    assert "8\nROOMS" in dxf_content
    assert "8\nWALLS" in dxf_content
    assert "8\nDOORS" in dxf_content
    assert "8\nWINDOWS" in dxf_content
    assert "8\nROOM_LABELS" in dxf_content
    
    # Assert text labels are exported
    assert "1\nBEDROOM" in dxf_content
    assert "1\nBATHROOM" in dxf_content
