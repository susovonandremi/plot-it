import os
import logging
import json
import uuid
import aiosqlite
try:
    import asyncpg
except ImportError:
    asyncpg = None
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Determine if we should use PostgreSQL (production/staging) or SQLite (local dev)
DATABASE_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

if IS_POSTGRES and asyncpg is None:
    raise ImportError(
        "PostgreSQL DATABASE_URL is configured, but the 'asyncpg' package is not installed. "
        "Please install it using 'pip install asyncpg' or unset the DATABASE_URL environment variable."
    )

# SQLite fallback path configuration
# Anchor SQLite DB to the absolute path of the backend workspace folder
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(backend_dir, "plotit_projects.db")

async def get_db_connection():
    """
    Returns a connected SQLite database with WAL and busy timeout configured.
    Only called when not using PostgreSQL.
    """
    db = await aiosqlite.connect(DB_FILE)
    # Enable Write-Ahead Logging (WAL) for concurrency
    await db.execute("PRAGMA journal_mode=WAL;")
    # Set busy timeout to 5000ms to resolve lockups
    await db.execute("PRAGMA busy_timeout=5000;")
    return db

async def init_db():
    """Initializes the database schema and performs lightweight migrations if necessary."""
    if IS_POSTGRES:
        assert asyncpg is not None
        logger.info("Initializing PostgreSQL database...")
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id VARCHAR(255) PRIMARY KEY,
                name TEXT,
                prompt TEXT,
                svg TEXT,
                scores JSONB,
                created_at TIMESTAMP,
                owner_id VARCHAR(255) DEFAULT 'anonymous'
            )
        """)
        # Dynamic migration: check if owner_id column exists
        try:
            await conn.execute("ALTER TABLE projects ADD COLUMN owner_id VARCHAR(255) DEFAULT 'anonymous'")
            logger.info("Successfully verified/added 'owner_id' column in PostgreSQL")
        except Exception:
            # Column already exists or other error
            pass
        await conn.close()
    else:
        logger.info(f"Initializing SQLite database at: {DB_FILE}")
        async with await get_db_connection() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    prompt TEXT,
                    svg TEXT,
                    scores JSON,
                    created_at TIMESTAMP,
                    owner_id TEXT DEFAULT 'anonymous'
                )
            """)
            await db.commit()
            
            # Dynamic migration: verify if owner_id column exists
            try:
                await db.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT DEFAULT 'anonymous'")
                await db.commit()
                logger.info("Successfully added 'owner_id' column in SQLite")
            except Exception:
                # Column already exists
                pass

async def save_project(project: Dict[str, Any]) -> str:
    """Saves a project (creates new or updates existing) bound to its owner_id."""
    project_id = project.get("id", str(uuid.uuid4()))
    name = project.get("name", f"Project {project_id[:8]}")
    prompt = project.get("prompt", "")
    svg = project.get("svg", "")
    if isinstance(svg, dict):
        svg = json.dumps(svg)
        
    scores = json.dumps(project.get("scores", {}))
    created_at = datetime.now(timezone.utc).isoformat()
    owner_id = project.get("owner_id", "anonymous")

    if IS_POSTGRES:
        assert asyncpg is not None
        conn = await asyncpg.connect(DATABASE_URL)
        await conn.execute("""
            INSERT INTO projects (id, name, prompt, svg, scores, created_at, owner_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO UPDATE SET 
                name = EXCLUDED.name, 
                prompt = EXCLUDED.prompt, 
                svg = EXCLUDED.svg, 
                scores = EXCLUDED.scores, 
                created_at = EXCLUDED.created_at, 
                owner_id = EXCLUDED.owner_id
        """, project_id, name, prompt, svg, scores, created_at, owner_id)
        await conn.close()
    else:
        async with await get_db_connection() as db:
            await db.execute("""
                INSERT OR REPLACE INTO projects (id, name, prompt, svg, scores, created_at, owner_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project_id, name, prompt, svg, scores, created_at, owner_id))
            await db.commit()
    
    return project_id

async def list_projects(owner_id: str = "anonymous", limit: int = 20) -> List[Dict[str, Any]]:
    """Lists recent projects filtered by the owner_id."""
    if IS_POSTGRES:
        assert asyncpg is not None
        conn = await asyncpg.connect(DATABASE_URL)
        rows = await conn.fetch(
            "SELECT id, name, prompt, scores, created_at, owner_id FROM projects WHERE owner_id = $1 ORDER BY created_at DESC LIMIT $2",
            owner_id, limit
        )
        await conn.close()
        projects = []
        for row in rows:
            proj = dict(row.items())
            if proj.get("scores"):
                proj["scores"] = json.loads(proj["scores"])
            projects.append(proj)
        return projects
    else:
        async with await get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, name, prompt, scores, created_at, owner_id FROM projects WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?", 
                (owner_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                
                projects = []
                for row in rows:
                    proj = dict(row)
                    if proj.get("scores"):
                        proj["scores"] = json.loads(proj["scores"])
                    projects.append(proj)
                return projects

async def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """Gets a project by its project_id."""
    if IS_POSTGRES:
        assert asyncpg is not None
        conn = await asyncpg.connect(DATABASE_URL)
        row = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
        await conn.close()
        if row:
            proj = dict(row.items())
            if proj.get("scores"):
                proj["scores"] = json.loads(proj["scores"])
            return proj
        return None
    else:
        async with await get_db_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    proj = dict(row)
                    if proj.get("scores"):
                        proj["scores"] = json.loads(proj["scores"])
                    return proj
                return None

async def delete_project(project_id: str) -> bool:
    """Deletes a project by its project_id."""
    if IS_POSTGRES:
        assert asyncpg is not None
        conn = await asyncpg.connect(DATABASE_URL)
        status = await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
        await conn.close()
        # status usually returns 'DELETE 1' or similar
        return " 0" not in status and "DELETE 0" not in status
    else:
        async with await get_db_connection() as db:
            cursor = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            await db.commit()
            return cursor.rowcount > 0