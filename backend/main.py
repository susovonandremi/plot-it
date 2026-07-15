import os
import logging
import sys

# Configure stdout and stderr to support unicode characters/emojis on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s"
)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from limiter import limiter

from routes import parse, consultation, generate, stream, export, projects
from services.project_store import init_db

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=dotenv_path)

app = FastAPI(
    title="PlotIt API",
    description="Natural language to 2D blueprint generator — CP-SAT Solver v4.0",
    version="4.0.0"
)

# 1. Configure CORS (ABSOLUTE TOP to handle cross-origin preflight SUCCESS)
allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Configure SlowAPI
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 3. 10KB Request Body Limit Middleware (placed below CORS to avoid preflight issues)
@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 51200:
        return JSONResponse(status_code=413, content={"detail": "Payload Too Large: maximum allowed size is 50KB"})
    return await call_next(request)

# Register routes
app.include_router(parse.router, prefix="/api/v1")
app.include_router(consultation.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(stream.router, prefix="/api/v1/stream")  # WebSocket streaming
app.include_router(export.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/health")
def health_check():
    from services.nlp_parser import is_llm_configured
    return {
        "status": "PlotIt backend is running",
        "version": "4.0.0",
        "llm_configured": is_llm_configured(),
        "features": [
            "cpsat_constraint_solver", "circulation_engine", "vastu_heatmap",
            "style_presets", "websocket_streaming", "structural_layer",
            "diff_engine", "blueprint_scorer", "furniture_engine",
            "accessibility_engine", "solar_wind_analysis", "isometric_preview"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
