import asyncio
import cv2
import time
from typing import Dict, Any, List
from app.processor import VideoProcessor
from app.scanner import scan_onvif_ws_discovery, scan_rtsp_ports, verify_rtsp_stream

class CameraStreamManager:
    def __init__(self, processor: VideoProcessor):
        self.processor = processor
        self.streams: Dict[str, Dict[str, Any]] = {}
        self.active_tasks: Dict[str, bool] = {}
        self.latest_frames: Dict[str, bytes] = {}
        self.latest_metadata: Dict[str, Dict[str, Any]] = {}

    def add_stream(self, stream_id: str, url: str) -> bool:
        """
        Adds a CCTV camera stream URL.
        """
        self.streams[stream_id] = {
            "stream_id": stream_id,
            "url": url,
            "added_at": time.time(),
            "status": "configured"
        }
        self.active_tasks[stream_id] = True
        return True

    def remove_stream(self, stream_id: str):
        if stream_id in self.streams:
            self.active_tasks[stream_id] = False
            del self.streams[stream_id]
            if stream_id in self.latest_frames:
                del self.latest_frames[stream_id]
            if stream_id in self.latest_metadata:
                del self.latest_metadata[stream_id]

    async def scan_and_register_cameras(self) -> List[Dict[str, Any]]:
        """
        Scans local network for ONVIF and RTSP CCTV cameras and registers valid streams.
        """
        print("Starting ONVIF WS-Discovery...")
        discovered = scan_onvif_ws_discovery(timeout=1.5)

        print("Scanning local RTSP ports...")
        rtsp_devices = scan_rtsp_ports(timeout=0.2)
        discovered.extend(rtsp_devices)

        verified = []
        for dev in discovered:
            url = dev["rtsp_url"]
            ip = dev["ip"]
            stream_id = f"cam_{ip.replace('.', '_')}"

            # Verify if stream can be opened
            if verify_rtsp_stream(url):
                dev["verified"] = True
                self.add_stream(stream_id, url)
                verified.append(dev)
            else:
                dev["verified"] = False
                verified.append(dev)

        return verified

    def start_processing_loop(self, stream_id: str):
        """
        Processes camera frames continuously for a stream.
        """
        if stream_id not in self.streams:
            return

        url = self.streams[stream_id]["url"]
        cap = cv2.VideoCapture(url)

        if not cap.isOpened():
            self.streams[stream_id]["status"] = "offline/error"
            print(f"Failed to open video stream: {url}")
            return

        self.streams[stream_id]["status"] = "streaming"

        while self.active_tasks.get(stream_id, False):
            ret, frame = cap.read()
            if not ret or frame is None:
                self.streams[stream_id]["status"] = "stream_interrupted"
                time.sleep(0.5)
                # Retry connection
                cap.release()
                cap = cv2.VideoCapture(url)
                continue

            self.streams[stream_id]["status"] = "active"

            # Run tracking and activity detection
            processed_frame, metadata = self.processor.process_frame(stream_id, frame)

            # Encode frame to JPEG
            ret_encode, buffer = cv2.imencode('.jpg', processed_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            if ret_encode:
                self.latest_frames[stream_id] = buffer.tobytes()
                self.latest_metadata[stream_id] = metadata

            time.sleep(0.03)  # cap frame rate to ~30 FPS

        cap.release()
        self.streams[stream_id]["status"] = "stopped"

    def get_latest_frame(self, stream_id: str) -> bytes:
        return self.latest_frames.get(stream_id, b'')

    def get_latest_metadata(self, stream_id: str) -> Dict[str, Any]:
        return self.latest_metadata.get(stream_id, {})
