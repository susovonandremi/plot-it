import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from services.nlp_parser import parse_prompt
from limiter import limiter

logger = logging.getLogger(__name__)

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
        correlation_id = uuid.uuid4().hex[:8]
        logger.error(f"Parse error [CID:{correlation_id}]: {str(e)}", exc_info=True)
        return {
            "success": False,
            "data": None,
            "error": {
                "code": "PARSE_ERROR",
                "message": f"An error occurred while parsing the prompt. Reference ID: {correlation_id}"
            }
        }
