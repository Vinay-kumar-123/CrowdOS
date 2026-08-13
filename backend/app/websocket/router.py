from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.websocket.manager import ws_manager
from app.core.logger import logger

ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WS payload: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
