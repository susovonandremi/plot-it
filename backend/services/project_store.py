import logging
import aiosqlite
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_FILE = "plotai_projects.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                prompt TEXT,
                svg TEXT,
                scores JSON,
                created_at TIMESTAMP
            )
        """)
        await db.commit()

async def save_project(project: Dict[str, Any]) -> str:
    project_id = project.get("id", str(uuid.uuid4()))
    name = project.get("name", f"Project {project_id[:8]}")
    prompt = project.get("prompt", "")
    svg = project.get("svg", "")
    scores = json.dumps(project.get("scores", {}))
    created_at = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR REPLACE INTO projects (id, name, prompt, svg, scores, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, name, prompt, svg, scores, created_at))
        await db.commit()
    
    return project_id

async def list_projects(limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, name, prompt, scores, created_at FROM projects ORDER BY created_at DESC LIMIT ?", 
            (limit,)
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
    async with aiosqlite.connect(DB_FILE) as db:
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
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
        return cursor.rowcount > 0