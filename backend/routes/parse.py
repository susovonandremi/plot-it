from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.nlp_parser import parse_prompt
from limiter import limiter

router = APIRouter()

class ParseRequest(BaseModel):
    prompt: str

@router.post("/parse")
@limiter.limit("30/minute")
async def parse_endpoint(request: Request, request_data: ParseRequest):
    """
    Parses natural language prompt into structured JSON.
    Detects incomplete input and triggers consultation mode.
    """
    try:
        result = parse_prompt(request_data.prompt)
        return {
            "success": True,
            "data": result,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "PARSE_ERROR",
                "message": str(e)
            }
        }
