from fastapi import APIRouter
from pydantic import BaseModel
from services.nlp_parser import analyze_consultation_answers

router = APIRouter()

from typing import Optional, Dict

class ConsultationRequest(BaseModel):
    plot_size_sqft: Optional[float] = None
    plot_width_ft: Optional[float] = None
    plot_depth_ft: Optional[float] = None
    entry_direction: Optional[str] = "N"
    orientation: Optional[str] = "unknown"
    answers: Dict

@router.post("/consultation/recommend")
async def get_room_recommendation(request: ConsultationRequest):
    """
    Takes user's consultation answers and returns recommended room list.
    """
    try:
        # Determine plot_size: prefer request field, fall back to answer fields
        plot_size = request.plot_size_sqft
        if not plot_size:
            # Try extracting from answers (question IDs like q3_plot_size, q1_plot_area, etc.)
            for key, value in request.answers.items():
                if 'plot' in key.lower() or 'area' in key.lower() or 'size' in key.lower():
                    try:
                        # Extract numeric value from answer string like "1200 sqft" or "1200"
                        numeric_str = ''.join(c for c in str(value) if c.isdigit() or c == '.')
                        if numeric_str:
                            plot_size = float(numeric_str)
                            break
                    except (ValueError, TypeError):
                        pass
        
        # Default fallback if still None
        if not plot_size or plot_size <= 0:
            plot_size = 1200
        
        plot_data = {
            "plot_size_sqft": plot_size,
            "plot_width_ft": request.plot_width_ft,
            "plot_depth_ft": request.plot_depth_ft,
            "entry_direction": request.entry_direction or "N",
            "orientation": request.orientation or "unknown"
        }
        recommendation = analyze_consultation_answers(plot_data, request.answers)
        # Ensure we return the dimensions back
        # Ensure plot_size is explicitly returned so frontend doesn't lose it
        recommendation['plot_size_sqft'] = plot_size
        recommendation['plot_width_ft'] = request.plot_width_ft
        recommendation['plot_depth_ft'] = request.plot_depth_ft
        recommendation['entry_direction'] = request.entry_direction or "N"
        return {
            "success": True,
            "data": recommendation,
            "error": None
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "CONSULTATION_ERROR",
                "message": str(e)
            }
        }
