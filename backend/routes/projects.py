from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from services.project_store import list_projects, get_project, delete_project

router = APIRouter()

@router.get("/projects")
async def handle_list_projects(limit: int = Query(20, ge=1, le=100)):
    projects = await list_projects(limit=limit)
    return {"success": True, "data": projects, "error": None}

@router.get("/projects/{project_id}")
async def handle_get_project(project_id: str):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "data": project, "error": None}

@router.delete("/projects/{project_id}")
async def handle_delete_project(project_id: str):
    success = await delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "data": {"deleted": project_id}, "error": None}
