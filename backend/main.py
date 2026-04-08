import os
import logging

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
import os
import logging

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
    title="PlotAI API",
    description="Natural language to 2D blueprint generator — Genius-Level v2.0",
    version="2.0.0"
)

# 1. Configure CORS (ABSOLUTE TOP to handle cross-origin preflight SUCCESS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    if content_length and int(content_length) > 10240:
        return JSONResponse(status_code=413, content={"detail": "Payload Too Large: maximum allowed size is 10KB"})
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
    return {
        "status": "PlotAI backend is running",
        "version": "2.0.0",
        "features": ["circulation_engine", "vastu_heatmap", "style_presets", "websocket_streaming", "structural_layer", "diff_engine"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
