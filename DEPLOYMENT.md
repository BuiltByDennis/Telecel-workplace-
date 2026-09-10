# CCTV Smart Vision & Activity Tracker - Deployment Guide

This guide explains how to run and deploy the CCTV Smart Vision & Activity Tracker system.

---

## 🏗️ Architecture Overview

The system consists of two main components:

1. **Local AI Tracking & Scanner Engine (Python / FastAPI / YOLOv8 / OpenCV)**:
   - Must run on the local network where CCTV cameras (ONVIF / RTSP) are reachable.
   - Performs real-time frame capture, YOLOv8 object tracking, movement analysis, and structured JSON event logging.
   - Provides REST & MJPEG streaming endpoints (`http://<local-ip>:8000`).

2. **Mobile Web Dashboard (Frontend)**:
   - Can be hosted locally or deployed globally on **Vercel**.
   - Connects to your local CCTV tracking engine to view live feeds, camera discovery, and structured activity logs.

---

## 🚀 1. Deploying Frontend Dashboard to Vercel

### Option A: Deploy via Vercel CLI

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy project
vercel
```

### Option B: Deploy via GitHub / GitLab Repository
1. Push your repository to GitHub / GitLab.
2. Go to [Vercel Dashboard](https://vercel.com/new).
3. Import your repository.
4. Set the Root Directory to `./` and Vercel will automatically deploy the static dashboard from `frontend/` using `vercel.json`.

---

## 🖥️ 2. Running the Local CCTV AI Engine

Since local CCTV cameras (ONVIF/RTSP) are located inside your local network subnet (e.g. `192.168.x.x`), the computer vision backend runs on your local server/laptop on the same network.

```bash
# Install dependencies
pip install -r requirements.txt

# Start the FastAPI engine
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## 📱 3. Accessing from Mobile Phone

1. Ensure your phone is connected to the same Wi-Fi network as the server running the AI engine.
2. Open your mobile browser and navigate to:
   - Local address: `http://<YOUR_SERVER_LOCAL_IP>:8000`
   - Or open your Vercel URL and configure your local engine address.
