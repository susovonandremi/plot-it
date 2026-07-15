# backend/tests/test_export_route.py
import pytest
import sys
import os
from starlette.requests import Request
from main import app
from routes.export import export_svg, ExportRequest

@pytest.mark.anyio
async def test_export_endpoint_dxf():
    floor_plan = {
        "metadata": {
            "plot_width_ft": 20.0,
            "plot_height_ft": 30.0,
            "floor_label": "GROUND FLOOR",
            "unit_system": "imperial",
            "vastu_score": {"overall": 85}
        },
        "rooms": [
            {"id": "bed_1", "label": "BEDROOM", "x": 0, "y": 0, "width": 10, "height": 12, "type": "bedroom", "area_sqft": 120, "vastu_zone": "NW", "floor_material": "hardwood"},
        ],
        "walls": {
            "boundary_polygon_wkt": "POLYGON ((0 0, 20 0, 20 30, 0 30, 0 0))"
        },
        "doors": [],
        "windows": [],
        "fixtures": [],
        "structural": {
            "columns": [],
            "beams": []
        },
        "site_context": {
            "setback_ft": 5.0,
            "entry_side": "N",
            "road_side": "N",
            "entry_room_id": "bed_1"
        },
        "dimension_chains": {
            "top_facade": [],
            "left_facade": [],
            "overall_width": {"value_ft": 20.0, "label": "20'-0\""},
            "overall_depth": {"value_ft": 30.0, "label": "30'-0\""}
        }
    }
    
    request_data = ExportRequest(
        floor_plan=floor_plan,
        format="dxf"
    )
    
    response = await export_svg(request_data)
    assert response.status_code == 200
    assert response.media_type == "application/dxf"
    assert "attachment; filename=\"blueprint.dxf\"" in response.headers["Content-Disposition"]
    
    content = response.body.decode("utf-8")
    assert content.startswith("0\nSECTION\n2\nENTITIES")
    assert content.endswith("0\nEOF\n")
