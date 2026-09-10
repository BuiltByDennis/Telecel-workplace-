import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading

from app.processor import VideoProcessor
from app.scanner import scan_onvif_ws_discovery, scan_rtsp_ports
from app.manager import CameraStreamManager

app = FastAPI(title="CCTV Smart Vision & Activity Tracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

processor = VideoProcessor()
manager = CameraStreamManager(processor)

class AddStreamRequest(BaseModel):
    stream_id: str
    url: str

class ScanRequest(BaseModel):
    subnet_prefix: Optional[str] = "192.168.1"

@app.get("/api/health")
def health_check():
    return {"status": "ok", "active_streams": len(manager.streams)}

@app.post("/api/scan")
async def scan_network(req: ScanRequest):
    discovered_onvif = scan_onvif_ws_discovery(timeout=1.5)
    discovered_rtsp = scan_rtsp_ports(subnet_prefix=req.subnet_prefix or "192.168.1", timeout=0.2)
    all_discovered = discovered_onvif + discovered_rtsp
    return {"count": len(all_discovered), "devices": all_discovered}

@app.get("/api/streams")
def list_streams():
    return {"streams": list(manager.streams.values())}

@app.post("/api/streams/add")
def add_stream(req: AddStreamRequest, background_tasks: BackgroundTasks):
    manager.add_stream(req.stream_id, req.url)
    t = threading.Thread(target=manager.start_processing_loop, args=(req.stream_id,), daemon=True)
    t.start()
    return {"status": "success", "message": f"Stream {req.stream_id} added."}

@app.delete("/api/streams/{stream_id}")
def remove_stream(stream_id: str):
    manager.remove_stream(stream_id)
    return {"status": "success", "message": f"Stream {stream_id} removed."}

@app.get("/api/streams/{stream_id}/metadata")
def get_stream_metadata(stream_id: str):
    metadata = manager.get_latest_metadata(stream_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Stream metadata not available")
    return metadata

@app.get("/api/logs")
def get_event_logs():
    return {"logs": processor.get_logs()}

def generate_mjpeg_stream(stream_id: str):
    import time
    while True:
        frame_bytes = manager.get_latest_frame(stream_id)
        if frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.04)

@app.get("/api/streams/{stream_id}/video")
def video_feed(stream_id: str):
    if stream_id not in manager.streams:
        raise HTTPException(status_code=404, detail="Stream ID not found")
    return StreamingResponse(generate_mjpeg_stream(stream_id),
                             media_type="multipart/x-mixed-replace; boundary=frame")

# Serve frontend static assets under /
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
