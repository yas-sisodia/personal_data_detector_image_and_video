

# ==========================================================

# tailscale funnel 8000


# tailscale funnel reset

# tailscale serve --bg --set-path /api http://127.0.0.1:8000
# tailscale serve --bg --set-path /streamlit http://127.0.0.1:8501

# tailscale funnel on

#   tailscale serve --https=443 off

# tailscale serve --bg --https=8443 http://127.0.0.1:8501
# tailscale funnel 8443 on

# https://yas.tail538282.ts.net:8443

# tailscale serve status




from fastapi import FastAPI, WebSocket, UploadFile
import shutil
import uuid
import os
import traceback
import sys
import asyncio
from typing import Any
from pathlib import Path
from starlette.websockets import WebSocketDisconnect




sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from backend.core.image_pipeline import run_image_pipeline  # next step
from backend.core.video_pipeline import run_video_pipeline  # next step
# from core.image_pipeline import run_image_pipeline  # next step
# from core.video_pipeline import run_video_pipeline  # next step


from contextlib import asynccontextmanager
from backend.core.model_manager import load_all_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting up... Ensuring models exist.")
    
    load_all_models()  # download only
    
    print("✅ Models ready.")

    yield  # <-- App runs here

    print("🛑 Shutting down...")

app = FastAPI(lifespan=lifespan)



from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_PATH = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_PATH / "backend" / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Upload endpoint (image + video)
# ==========================================================
@app.post("/upload")
async def upload_file(file: UploadFile):
    file_id = str(uuid.uuid4())
    file_name = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / file_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "file_name": file_name,
        "content_type": file.content_type
    }






# ==========================================================
# WebSocket analysis endpoint
# ==========================================================

@app.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket):
    await websocket.accept()
    print("✅ WebSocket connected")

    try:
        data = await websocket.receive_json()

        file_id = data["file_id"]
        file_type = data.get("file_type", "image")
        enable_caption = data.get("enable_caption", False)

        file_path = os.path.join(UPLOAD_DIR, file_id)

        if not os.path.exists(file_path):
            await websocket.send_json({
                "type": "error",
                "message": "File not found"
            })
            return

        async def progress_cb(step, percent, other_data=None):
            payload = {
                "type": "progress",
                "step": step,
                "percent": percent,
                "other_data": other_data
            }

            try:
                print(f"Progress: {step} ({percent}%)")
                await websocket.send_json(payload)

                # Give the event loop a chance to process ping/pong
                await asyncio.sleep(0)

            except WebSocketDisconnect:
                print("⚠️ Client disconnected.")
                raise

            except RuntimeError:
                # Socket already closed
                raise WebSocketDisconnect()

        # ----------------------------
        # Run pipeline
        # ----------------------------
        if file_type == "video":
            print("🎥 Running video pipeline")

            result = await run_video_pipeline(
                file_path,
                progress_cb=progress_cb,
                enable_caption=enable_caption
            )

        else:
            print("🖼️ Running image pipeline")

            result = await run_image_pipeline(
                file_path,
                progress_cb=progress_cb,
                enable_caption=enable_caption
            )

        try:
            await websocket.send_json({
                "type": "result",
                "data": result
            })

        except WebSocketDisconnect:
            print("Client disconnected before final result.")

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected.")

    except Exception as e:
        traceback.print_exc()

        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except (WebSocketDisconnect, RuntimeError):
            pass

    finally:
        try:
            await websocket.close()
        except RuntimeError:
            # Already closed
            pass

        print("🔌 WebSocket closed")
# ==========================================================
# WebSocket analysis endpoint
# ==========================================================



# @app.websocket("/ws/analyze")
# async def websocket_analyze(websocket: WebSocket):
#     await websocket.accept()
#     print("✅ WebSocket connected")

#     try:
#         data = await websocket.receive_json()
#         file_id = data["file_id"]
#         file_type = data.get("file_type", "image")  # default image
#         enable_caption = data.get("enable_caption", False)

#         file_path = os.path.join(UPLOAD_DIR, file_id)

#         if not os.path.exists(file_path):
#             await websocket.send_json({
#                 "type": "error",
#                 "message": "File not found"
#             })
#             await websocket.close()
#             return

#         async def progress_cb(step: str, percent: int, other_data: dict[str, Any] | None):
#             data = {
#                 "type": "progress",
#                 "step": step,
#                 "percent": percent, 
#                 "other_data":other_data
#             }
#             print(f"Emitting progress: {data}")
#             await websocket.send_json(data)
#             await asyncio.sleep(0.05)

#         # ---------------- ROUTING ----------------
#         if file_type == "video":
#             print("🎥 Running video pipeline")
#             result = await run_video_pipeline(
#                 file_path,
#                 progress_cb=progress_cb,
#                 enable_caption=enable_caption
#             )
#         else:
#             print("🖼️ Running image pipeline")
#             result = await run_image_pipeline(
#                 file_path,
#                 progress_cb=progress_cb,
#                 enable_caption=enable_caption
#             )

#         await websocket.send_json({
#             "type": "result",
#             "data": result
#         })

#     except Exception as e:
#         traceback.print_exc()
#         await websocket.send_json({
#             "type": "error",
#             "message": str(e)
#         })

#     finally:
#         await websocket.close()
#         print("🔌 WebSocket closed")





if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws_ping_interval=300,
        ws_ping_timeout=420,
    )




    