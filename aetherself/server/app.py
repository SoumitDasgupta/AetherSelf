"""FastAPI application providing REST & WebSockets for AetherSelf operations dashboard."""

import os
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from ..daemon import AetherSelfDaemon
from ..types import ModelTier


class FaultRequest(BaseModel):
    fault_type: str


class ModelSwitchRequest(BaseModel):
    tier: str  # "TIER_1_ROUTINE_1B" or "TIER_2_DIAGNOSTIC_3_8B"


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 3


def create_app(daemon: Optional[AetherSelfDaemon] = None) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="AetherSelf Edge Operations Hub",
        description="Autonomous Self-Healing Edge Agent Framework Dashboard & Control API",
        version="1.0.0",
    )

    if daemon is None:
        daemon = AetherSelfDaemon()

    app.state.daemon = daemon
    active_websockets: List[WebSocket] = []

    # Forward daemon events to connected WebSocket clients
    def _ws_broadcaster(payload: dict):
        if not active_websockets:
            return
        msg = json.dumps(payload)
        disconnected = []
        for ws in active_websockets:
            try:
                asyncio.create_task(ws.send_text(msg))
            except Exception:
                disconnected.append(ws)
        for dead in disconnected:
            if dead in active_websockets:
                active_websockets.remove(dead)

    daemon.register_broadcast_callback(_ws_broadcaster)

    @app.on_event("startup")
    async def startup_event():
        await daemon.start()

    @app.on_event("shutdown")
    async def shutdown_event():
        await daemon.stop()

    @app.get("/api/status")
    async def get_status():
        """Retrieve real-time status snapshot."""
        return daemon.get_dashboard_summary()

    @app.post("/api/fault/inject")
    async def inject_fault(req: FaultRequest):
        """Inject chaos fault into simulated microservice cluster."""
        try:
            res = daemon.fault_injector.inject(req.fault_type)
            return {"status": "ok", "injection": res}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/fault/clear")
    async def clear_faults():
        """Clear all active faults and reset cluster."""
        daemon.fault_injector.clear_all()
        daemon.state_machine.reset_to_normal("Faults cleared manually")
        return {"status": "ok", "message": "All faults cleared and cluster normalized."}

    @app.post("/api/model/switch")
    async def switch_model(req: ModelSwitchRequest):
        """Manually trigger SLM tier switch."""
        try:
            tier = ModelTier(req.tier)
            daemon.model_switcher.force_tier(tier, reason="Manual operator override from UI")
            return {"status": "ok", "active_tier": tier.value}
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tier '{req.tier}'")

    @app.post("/api/rag/search")
    async def rag_search(req: RAGQueryRequest):
        """Perform ad-hoc semantic query against vector database."""
        matches = daemon.rag.retrieve(req.query, top_k=req.top_k)
        return {
            "query": req.query,
            "count": len(matches),
            "matches": [m.model_dump() for m in matches],
        }

    @app.get("/api/rag/incidents")
    async def list_rag_incidents():
        """List all incidents currently indexed in vector memory."""
        incidents = [inc.model_dump() for inc in daemon.rag._store.incidents]
        return {
            "total_incidents": len(incidents),
            "incidents": incidents,
        }

    @app.websocket("/ws/telemetry")
    async def websocket_telemetry(websocket: WebSocket):
        """Real-time streaming channel for live telemetry, state transitions, and CoT logs."""
        await websocket.accept()
        active_websockets.append(websocket)
        # Send initial state snapshot immediately
        await websocket.send_text(json.dumps({
            "event": "initial_state",
            "data": daemon.get_dashboard_summary(),
        }))
        try:
            while True:
                # Keep socket alive and accept ping/pong or client commands
                data = await websocket.receive_text()
                try:
                    cmd = json.loads(data)
                    if cmd.get("action") == "inject":
                        daemon.fault_injector.inject(cmd.get("fault_type", "memory_leak"))
                    elif cmd.get("action") == "clear":
                        daemon.fault_injector.clear_all()
                except Exception:
                    pass
        except WebSocketDisconnect:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
        except Exception:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

    # Mount UI static files if directory exists
    web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))
    if os.path.exists(web_dir):
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

        @app.get("/", response_class=HTMLResponse)
        async def root():
            index_path = os.path.join(web_dir, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
            return "<h1>AetherSelf Edge Operations Hub</h1>"

    return app
