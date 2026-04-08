import io
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

router = APIRouter()

class ExportRequest(BaseModel):
    svg: str
    format: str

@router.post("/export")
async def export_svg(request: ExportRequest):
    if not request.svg:
        raise HTTPException(status_code=400, detail="SVG string is required.")
    
    fmt = request.format.lower()
    if fmt not in ["pdf", "png"]:
        raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'png'.")

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
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
