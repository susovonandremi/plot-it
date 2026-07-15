import io
import json
import logging
import uuid
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.dxf_exporter import export_to_dxf

logger = logging.getLogger(__name__)

router = APIRouter()

class ExportRequest(BaseModel):
    svg: Optional[str] = None
    floor_plan: Optional[Dict[str, Any]] = None
    format: str

@router.post("/export")
async def export_svg(request: ExportRequest):
    fmt = request.format.lower()
    
    if fmt == "dxf":
        # Resolve floor plan dict
        plan_data = None
        if request.floor_plan:
            plan_data = request.floor_plan
        elif request.svg:
            try:
                plan_data = json.loads(request.svg)
            except Exception:
                raise HTTPException(status_code=400, detail="For DXF format, 'svg' field must be a valid JSON representation of the FloorPlanSchema, or 'floor_plan' must be provided.")
        
        if not plan_data:
            raise HTTPException(status_code=400, detail="Floor plan data is required for DXF export.")

        try:
            dxf_string = export_to_dxf(plan_data)
            output_bytes = dxf_string.encode('utf-8')
            media_type = "application/dxf"
            filename = "blueprint.dxf"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
            return Response(content=output_bytes, media_type=media_type, headers=headers)
        except Exception as dxf_err:
            correlation_id = uuid.uuid4().hex[:8]
            logger.error(f"DXF export failed [CID:{correlation_id}]: {str(dxf_err)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"DXF export failed. Reference ID: {correlation_id}")

    # Legacy formats (PDF, PNG)
    if not request.svg:
        raise HTTPException(status_code=400, detail="SVG string is required.")
    
    if fmt not in ["pdf", "png"]:
        raise HTTPException(status_code=400, detail="Format must be 'pdf', 'png', or 'dxf'.")

    try:
        # Lazy import to avoid crash on start if Cairo binaries are missing
        try:
            import cairosvg
            if fmt == "pdf":
                output_bytes = cairosvg.svg2pdf(bytestring=request.svg.encode('utf-8'))
                media_type = "application/pdf"
                filename = "blueprint.pdf"
            elif fmt == "png":
                output_bytes = cairosvg.svg2png(bytestring=request.svg.encode('utf-8'))
                media_type = "image/png"
                filename = "blueprint.png"
        except (ImportError, OSError):
            # Fallback for PDF using svglib + reportlab if Cairo is missing
            if fmt == "pdf":
                from svglib.svglib import svg2rlg
                from reportlab.graphics import renderPDF
                drawing = svg2rlg(io.BytesIO(request.svg.encode('utf-8')))
                buf = io.BytesIO()
                renderPDF.drawToFile(drawing, buf)
                output_bytes = buf.getvalue()
                media_type = "application/pdf"
                filename = "blueprint.pdf"
            else:
                raise HTTPException(status_code=500, detail="PNG export requires Cairo libraries. Please install them on your system.")

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"'
        }

        return Response(content=output_bytes, media_type=media_type, headers=headers)
    
    except Exception as e:
        correlation_id = uuid.uuid4().hex[:8]
        logger.error(f"Export failed [CID:{correlation_id}]: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed. Reference ID: {correlation_id}")
