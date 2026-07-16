"""
Generation Route — v4.1 (Pipeline Delegation)
===============================================
Thin REST endpoint that delegates to the shared generation pipeline.
All layout orchestration logic lives in ``services/pipeline.py``.
"""

import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from services.auth import get_current_user
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from services.pipeline import PipelineParams, run_generation_pipeline
from services.style_engine import get_all_style_names
from limiter import limiter
from services.project_store import save_project

logger = logging.getLogger("plotit")
router = APIRouter()


# ── REQUEST MODELS ────────────────────────────────────────────────────────────

class RoomConfig(BaseModel):
    type: str
    count: Optional[int] = 1
    special_notes: Optional[str] = None


class PlotShapeConfig(BaseModel):
    type: str = "rectangle"
    cutout_width: Optional[float] = None
    cutout_height: Optional[float] = None
    cutout_corner: str = "NE"


class GenerateRequest(BaseModel):
    plot_size_sqft: float = Field(..., gt=0, lt=100000)
    floors: int = 1
    rooms: List[RoomConfig]
    user_tier: str = "free"
    original_unit_system: Optional[Dict[str, Any]] = None

    # Building context
    building_type: str = "independent_house"
    floor_number: int = 0
    entry_direction: str = "N"
    latitude: float = 12.0  # Default: South India
    has_lift: bool = False
    has_balcony: bool = False
    has_verandah: bool = False
    plot_width_ft: Optional[float] = None
    plot_depth_ft: Optional[float] = None
    plot_shape: Optional[PlotShapeConfig] = None

    # Feature C: Style preset
    architectural_style: Optional[str] = None

    # Feature D: Refinement diffing
    previous_layout: Optional[List[Dict[str, Any]]] = None

    # Feature flags (allow clients to opt-in/out of expensive features)
    enable_circulation: bool = True
    enable_heatmap: bool = True
    enable_structural: bool = True

    # v3.0: Layout mode — 'cpsat' (default)
    layout_mode: str = "cpsat"
    include_furniture: bool = True
    prompt: str = Field(..., min_length=10, max_length=2000)

# ── MAIN ENDPOINT ─────────────────────────────────────────────────────────────

@router.post("/generate")
@limiter.limit("10/minute")
async def generate_blueprint_endpoint(
    request: Request,
    request_data: GenerateRequest,
    format: str = "json",
    user_id: str = Depends(get_current_user)
):
    """
    End-to-end blueprint generation via the shared pipeline.
    """
    if format != "json":
        raise HTTPException(
            status_code=400,
            detail="The legacy raw SVG format has been deprecated. Please use format=json."
        )

    try:
        raw_rooms = [r.model_dump() for r in request_data.rooms]

        params = PipelineParams(
            plot_size_sqft=request_data.plot_size_sqft,
            floors=request_data.floors,
            rooms=raw_rooms,
            prompt=request_data.prompt,
            user_tier=request_data.user_tier,
            entry_direction=request_data.entry_direction,
            has_lift=request_data.has_lift,
            has_balcony=request_data.has_balcony,
            has_verandah=request_data.has_verandah,
            plot_width_ft=request_data.plot_width_ft,
            plot_depth_ft=request_data.plot_depth_ft,
            building_type=request_data.building_type,
            architectural_style=request_data.architectural_style,
            original_unit_system=request_data.original_unit_system,
            previous_layout=request_data.previous_layout,
            enable_circulation=request_data.enable_circulation,
            enable_heatmap=request_data.enable_heatmap,
            enable_structural=request_data.enable_structural,
            include_furniture=request_data.include_furniture,
            plot_shape=request_data.plot_shape.model_dump() if request_data.plot_shape else None,
            latitude=request_data.latitude,
            layout_mode=request_data.layout_mode,
            floor_number=request_data.floor_number,
        )

        result = await run_generation_pipeline(params)
        response_data = result.response_data

        # Auto-save project for history/gallery
        try:
            resolved_owner_id = "anonymous"
            if isinstance(user_id, str):
                resolved_owner_id = user_id

            project_id = await save_project({
                "prompt": request_data.prompt,
                "svg": result.schema_blueprint,
                "scores": {
                    "vastu": response_data["vastu_score"],
                    "blueprint_overall": response_data["blueprint_score"]["overall"],
                },
                "owner_id": resolved_owner_id,
            })
            response_data["project_id"] = project_id
        except Exception as save_err:
            logger.warning("Failed to auto-save project: %s", save_err)

        return {"success": True, "data": response_data, "error": None}

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        import traceback
        import uuid
        correlation_id = uuid.uuid4().hex[:8]
        error_trace = traceback.format_exc()
        logger.error("Generation failure [CID:%s]: %s\n%s", correlation_id, str(e), error_trace)
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during blueprint generation. Reference ID: {correlation_id}"
        )
    finally:
        pass


# ── UTILITY ENDPOINTS ─────────────────────────────────────────────────────────

@router.get("/styles")
async def list_styles():
    """Returns all available architectural style presets."""
    return {"success": True, "data": get_all_style_names()}
