# backend/tests/test_generate_route.py
import pytest
import sys
import os
from starlette.requests import Request
from main import app
from fastapi import HTTPException
from routes.generate import generate_blueprint_endpoint, GenerateRequest, RoomConfig

@pytest.mark.anyio
async def test_generate_endpoint_json_format():
    request_data = GenerateRequest(
        plot_size_sqft=1500.0,
        floors=1,
        rooms=[
            RoomConfig(type="bedroom", count=2),
            RoomConfig(type="bathroom", count=2),
            RoomConfig(type="kitchen", count=1),
            RoomConfig(type="living", count=1)
        ],
        user_tier="free",
        prompt="I want to build a house on a 30x50 plot facing North with 2 bedrooms and a kitchen."
    )
    
    # Initialize a real Request object using ASGI scope
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/generate",
        "headers": [],
        "app": app
    }
    mock_request = Request(scope)
    mock_request.state.limiter = app.state.limiter
    
    res = await generate_blueprint_endpoint(mock_request, request_data, format="json")
    assert res["success"] is True
    
    response_data = res["data"]
    assert "floor_plan" in response_data
    assert "floor_plans" in response_data
    assert "svg" not in response_data
    
    # Verify FloorPlanSchema structure
    floor_plan = response_data["floor_plan"]
    assert floor_plan["version"] == "1.0.0"
    assert "metadata" in floor_plan
    assert "rooms" in floor_plan
    assert "walls" in floor_plan
    assert "doors" in floor_plan
    assert "windows" in floor_plan
    assert "fixtures" in floor_plan
    assert "structural" in floor_plan
    assert "site_context" in floor_plan
    assert "dimension_chains" in floor_plan

    # Verify C1/C2/C4 Fix Correctness Assertions
    # 1. Non-annotation rooms in typical floor plan should contain all user-requested rooms
    physical_rooms = [r for r in floor_plan["rooms"] if not r.get("is_annotation", False)]
    room_types = [r["type"].lower().replace(" ", "_") for r in physical_rooms]
    assert room_types.count("bedroom") == 2
    assert room_types.count("bathroom") == 2
    assert room_types.count("kitchen") == 1
    assert room_types.count("living") == 1

    # 2. Score should NOT be capped at 49 (due to working doors & accessibility graph)
    assert response_data["blueprint_score"]["overall"] >= 50.0
    assert response_data["blueprint_score"]["grade"] != "F"

    # 3. Environment scoring should be resolved (non-zero due to setback coordination)
    assert response_data["environment"]["overall_sun_score"] > 0.0
    assert response_data["environment"]["overall_vent_score"] > 0.0

@pytest.mark.anyio
async def test_generate_endpoint_svg_format():
    request_data = GenerateRequest(
        plot_size_sqft=1500.0,
        floors=1,
        rooms=[
            RoomConfig(type="bedroom", count=2),
            RoomConfig(type="bathroom", count=2),
            RoomConfig(type="kitchen", count=1),
            RoomConfig(type="living", count=1)
        ],
        user_tier="free",
        prompt="I want to build a house on a 30x50 plot facing North with 2 bedrooms and a kitchen."
    )
    
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/generate",
        "headers": [],
        "app": app
    }
    mock_request = Request(scope)
    mock_request.state.limiter = app.state.limiter
    
    # SVG format should raise an HTTPException with status code 400 indicating deprecation
    with pytest.raises(HTTPException) as exc_info:
        await generate_blueprint_endpoint(mock_request, request_data, format="svg")
    
    assert exc_info.value.status_code == 400
    assert "deprecated" in exc_info.value.detail.lower()
