"""API router for A/B testing operations.

Exposes a small endpoint to trigger `route_and_execute` from `tools/ab_test`.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel
from tools.api_auth import require_api_key

router = APIRouter(prefix="/api/ab")


class ExecuteRequest(BaseModel):
    test_name: str
    actor: str
    symbol: str
    side: str
    qty: float
    price: float
    confidence: Optional[float] = None
    key: Optional[str] = None


@router.post("/execute")
def execute(req: ExecuteRequest = Body(...), caller: dict = Depends(require_api_key)):
    try:
        # scope check: allow admin or api_key with 'ab:execute' scope
        ctype = caller.get("type") if isinstance(caller, dict) else None
        if ctype == "api_key":
            scopes = caller.get("scopes") or []
            if "ab:execute" not in scopes:
                raise HTTPException(status_code=403, detail="API key missing required scope: ab:execute")
        elif ctype == "admin":
            pass
        else:
            # unknown caller type — deny
            raise HTTPException(status_code=403, detail="unauthorized caller")

        from tools import ab_test

        out = ab_test.route_and_execute(
            test_name=req.test_name,
            actor=req.actor,
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            price=req.price,
            confidence=req.confidence,
            key=req.key,
        )
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
