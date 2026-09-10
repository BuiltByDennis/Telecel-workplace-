import cv2
import time
import json
import os
import math
from typing import Dict, List, Any
from ultralytics import YOLO

class VideoProcessor:
    def __init__(self, model_path: str = "yolov8n.pt", log_file: str = "event_logs.json"):
        print(f"Initializing YOLO model from {model_path}...")
        self.model = YOLO(model_path)
        self.log_file = log_file

        # COCO class IDs of interest
        # 0: person
        # 62: laptop, 63: mouse, 66: keyboard, 67: cell phone, 68: microwave, 72: tv (monitors/computers)
        self.tracked_classes = {0: "Person", 62: "Laptop/Computer", 67: "Cell Phone", 72: "Computer Display"}

        # Track previous positions for movement vectoring
        self.previous_positions: Dict[str, List[tuple]] = {}

        # Event history log buffer
        self.event_logs: List[Dict[str, Any]] = []
        self._load_existing_logs()

    def _load_existing_logs(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    self.event_logs = json.load(f)
            except Exception:
                self.event_logs = []

    def _save_event_log(self, event: Dict[str, Any]):
        self.event_logs.append(event)
        # Keep recent 1000 logs in memory and JSON file
        if len(self.event_logs) > 1000:
            self.event_logs = self.event_logs[-1000:]

        try:
            with open(self.log_file, "w") as f:
                json.dump(self.event_logs, f, indent=2)
        except Exception as e:
            print(f"Error saving log: {e}")

    def process_frame(self, stream_id: str, frame) -> tuple[Any, Dict[str, Any]]:
        """
        Runs YOLO tracking on a frame, draws bounding boxes, vector movements,
        detects activities, and generates structured JSON metadata.
        """
        # Run YOLO with built-in ByteTrack / BoT-SORT tracker
        results = self.model.track(frame, persist=True, verbose=False, conf=0.35)

        current_time = time.time()
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time))

        tracked_objects = []
        activities_detected = []

        persons_count = 0
        computers_count = 0
        movements_detected = []

        if results and len(results) > 0:
            result = results[0]
            boxes = result.boxes

            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())

                    # Track ID assigned by ByteTrack
                    track_id = int(box.id[0].item()) if box.id is not None else None

                    # Coordinates [x1, y1, x2, y2]
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                    label = self.tracked_classes.get(cls_id, result.names.get(cls_id, f"Class {cls_id}"))

                    if cls_id == 0:
                        persons_count += 1
                    elif cls_id in [62, 72]:
                        computers_count += 1

                    # Calculate movement / velocity if track_id exists
                    speed = 0.0
                    movement_status = "Stationary"
                    if track_id is not None:
                        id_key = f"{stream_id}_{track_id}"
                        if id_key in self.previous_positions:
                            prev_x, prev_y, prev_t = self.previous_positions[id_key]
                            dt = current_time - prev_t
                            if dt > 0:
                                dist = math.sqrt((cx - prev_x)**2 + (cy - prev_y)**2)
                                speed = dist / dt  # pixels per second
                                if speed > 15.0:
                                    movement_status = "Moving"
                                    movements_detected.append({
                                        "track_id": track_id,
                                        "label": label,
                                        "speed_px_per_sec": round(speed, 2),
                                        "position": [cx, cy]
                                    })

                        self.previous_positions[id_key] = (cx, cy, current_time)

                    # Bounding Box Drawing
                    color = (0, 255, 0) if cls_id == 0 else (255, 165, 0) if cls_id in [62, 72] else (255, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                    # Label text overlay
                    id_str = f" #{track_id}" if track_id is not None else ""
                    text = f"{label}{id_str} ({conf:.2f}) - {movement_status}"
                    cv2.putText(frame, text, (x1, max(y1 - 10, 15)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                    tracked_objects.append({
                        "track_id": track_id,
                        "class_id": cls_id,
                        "label": label,
                        "confidence": round(conf, 2),
                        "bbox": [x1, y1, x2, y2],
                        "center": [cx, cy],
                        "status": movement_status,
                        "speed": round(speed, 2)
                    })

        # Categorize Environment Activities
        if persons_count > 0 and computers_count > 0:
            activities_detected.append("Person interacting near computer station")
        if persons_count > 3:
            activities_detected.append("High occupancy / group gathered")
        if len(movements_detected) > 0:
            activities_detected.append(f"{len(movements_detected)} active object(s) in motion")
        if persons_count == 0 and computers_count == 0:
            activities_detected.append("Area clear / idle")

        # Top Overlay Banner on frame
        info_text = f"Stream: {stream_id} | Persons: {persons_count} | Computers: {computers_count} | Movements: {len(movements_detected)}"
        cv2.putText(frame, info_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Structured JSON Metadata Payload
        metadata = {
            "stream_id": stream_id,
            "timestamp": timestamp_str,
            "unix_timestamp": current_time,
            "summary": {
                "persons_count": persons_count,
                "computers_count": computers_count,
                "total_movements": len(movements_detected)
            },
            "environment_activities": activities_detected,
            "movements": movements_detected,
            "objects": tracked_objects
        }

        # Log event if notable activity occurred
        if activities_detected or len(movements_detected) > 0:
            log_entry = {
                "timestamp": timestamp_str,
                "stream_id": stream_id,
                "activities": activities_detected,
                "summary": metadata["summary"]
            }
            self._save_event_log(log_entry)

        return frame, metadata

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.event_logs
