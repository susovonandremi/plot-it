from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any
from services.project_store import list_projects, get_project, delete_project
from services.auth import get_current_user, require_user

router = APIRouter()

@router.get("/projects")
async def handle_list_projects(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user)
):
    projects = await list_projects(owner_id=user_id, limit=limit)
    return {"success": True, "data": projects, "error": None}

@router.get("/projects/{project_id}")
async def handle_get_project(
    project_id: str,
    user_id: str = Depends(get_current_user)
):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # IDOR Check: Ensure project belongs to the current requester
    if project.get("owner_id", "anonymous") != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this project")
        
    return {"success": True, "data": project, "error": None}

@router.delete("/projects/{project_id}")
async def handle_delete_project(
    project_id: str,
    user_id: str = Depends(require_user)
):
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # IDOR Check: Ensure requester owns the project they are deleting
    if project.get("owner_id", "anonymous") != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this project")
        
    success = await delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True, "data": {"deleted": project_id}, "error": None}
