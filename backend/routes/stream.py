"""
WebSocket Streaming Route — Feature D: Real-Time Blueprint Generation
======================================================================
Thin WebSocket endpoint that delegates to the shared generation pipeline
in ``services/pipeline.py`` and streams generation progress events
to the frontend in real-time.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any

from services.pipeline import PipelineParams, run_generation_pipeline

logger = logging.getLogger("plotit.stream")
router = APIRouter()


async def _emit(ws: WebSocket, event: str, data: Dict[str, Any]):
    """Helper to send a JSON event over WebSocket."""
    await ws.send_text(json.dumps({"event": event, "data": data}))


@router.websocket("/generate")
async def stream_generate(ws: WebSocket):
    """
    WebSocket endpoint for streaming blueprint generation.

    Client sends a JSON payload identical to the POST /generate body.
    Server streams progress events and finally sends the complete blueprint.
    """
    await ws.accept()
    logger.info("WebSocket connection accepted")

    try:
        raw = await ws.receive_text()
        request_data = json.loads(raw)

        async def progress_callback(stage: str, progress: int, message: str):
            await _emit(ws, "stage", {
                "stage": stage,
                "progress": progress,
                "message": message
            })

        # Build pipeline params from the request payload
        params = PipelineParams(
            plot_size_sqft=float(request_data.get("plot_size_sqft") or 1200),
            floors=int(request_data.get("floors") or 1),
            rooms=request_data.get("rooms", []),
            prompt=request_data.get("prompt", ""),
            user_tier=request_data.get("user_tier", "free"),
            entry_direction=request_data.get("entry_direction", "N"),
            has_lift=request_data.get("has_lift", False),
            has_balcony=request_data.get("has_balcony", False),
            has_verandah=request_data.get("has_verandah", False),
            plot_width_ft=request_data.get("plot_width_ft"),
            plot_depth_ft=request_data.get("plot_depth_ft"),
            building_type=request_data.get("building_type", "independent_house"),
            architectural_style=request_data.get("architectural_style"),
            original_unit_system=request_data.get("original_unit_system"),
            previous_layout=request_data.get("previous_layout"),
            enable_circulation=request_data.get("enable_circulation", True),
            enable_heatmap=request_data.get("enable_heatmap", True),
            enable_structural=request_data.get("enable_structural", True),
            include_furniture=request_data.get("include_furniture", True),
            plot_shape=request_data.get("plot_shape"),
            latitude=float(request_data.get("latitude", 12.0)),
            layout_mode=request_data.get("layout_mode", "cpsat"),
            floor_number=int(request_data.get("floor_number") or 0),
            progress_callback=progress_callback
        )

        result = await run_generation_pipeline(params)
        response_data = result.response_data

        # Explicitly set the engine identifier for streaming context
        response_data["engine"] = "cpsat_stream_v4"

        await _emit(ws, "complete", response_data)
        logger.info("WebSocket generation complete")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except json.JSONDecodeError as e:
        await _emit(ws, "error", {"message": f"Invalid JSON payload: {str(e)}"})
    except ValueError as ve:
        await _emit(ws, "error", {"message": str(ve)})
    except Exception as e:
        import uuid
        import traceback
        correlation_id = uuid.uuid4().hex[:8]
        error_trace = traceback.format_exc()
        logger.error("WebSocket generation error [CID:%s]: %s\n%s", correlation_id, str(e), error_trace)
        try:
            await _emit(ws, "error", {
                "message": f"An unexpected error occurred during stream generation. Reference ID: {correlation_id}"
            })
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
