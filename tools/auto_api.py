"""API router for LLM-driven auto-execution pipeline.

Exposes `/api/auto/execute` which triggers `tools.auto_exec.run_llm_auto_pipeline`.
Protected by API key auth and requires `auto:execute` scope for API keys.
"""
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/auto")

try:
    from tools.api_auth import require_api_key
except Exception:
    def require_api_key(*_args, **_kwargs):
        raise HTTPException(status_code=503, detail="API authentication unavailable")


class AutoExecRequest(BaseModel):
    user: str
    symbols: List[str]
    horizon: Optional[str] = "1d"
    dry_run: Optional[bool] = True
    auto_execute: Optional[bool] = False


@router.post("/execute")
def execute(req: AutoExecRequest = Body(...), caller: dict = Depends(require_api_key)):
    # scope check
    ctype = caller.get("type") if isinstance(caller, dict) else None
    if ctype == "api_key":
        scopes = caller.get("scopes") or []
        if "auto:execute" not in scopes:
            raise HTTPException(status_code=403, detail="API key missing required scope: auto:execute")
    elif ctype != "admin":
        raise HTTPException(status_code=403, detail="unauthorized caller")

    try:
        from tools import auto_exec

        out = auto_exec.run_llm_auto_pipeline(user=req.user, symbols=req.symbols, horizon=req.horizon, dry_run=bool(req.dry_run), auto_execute=bool(req.auto_execute))
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
