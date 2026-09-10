import socket
import cv2
import threading
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

def scan_onvif_ws_discovery(timeout: float = 1.5) -> List[Dict[str, Any]]:
    ws_discovery_msg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:d="http://schemas.xmlsoap.org/ws/2004/08/discovery">'
        '<e:Header>'
        '<w:MessageID>uuid:84567890-1234-5678-9012-123456789012</w:MessageID>'
        '<w:To>urn:schemas-xmlsoap-org:ws:2004:08:discovery</w:To>'
        '<w:Action>http://schemas.xmlsoap.org/ws/2004/08/discovery/Probe</w:Action>'
        '</e:Header>'
        '<e:Body>'
        '<d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe>'
        '</e:Body>'
        '</e:Envelope>'
    )

    found_devices = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.settimeout(timeout)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    try:
        sock.sendto(ws_discovery_msg.encode('utf-8'), ('239.255.255.250', 3702))
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(65535)
                ip = addr[0]
                content = data.decode('utf-8', errors='ignore')
                found_devices.append({
                    "ip": ip,
                    "type": "ONVIF",
                    "raw_response": content,
                    "rtsp_url": f"rtsp://{ip}:554/live"
                })
            except socket.timeout:
                break
            except Exception:
                pass
    except Exception as e:
        print(f"WS-Discovery error: {e}")
    finally:
        sock.close()

    return found_devices


def scan_rtsp_ports(subnet_prefix: str = "192.168.1", ports: List[int] = [554, 8554, 8000], timeout: float = 0.2) -> List[Dict[str, Any]]:
    discovered = []
    lock = threading.Lock()

    def check_ip_port(ip: str, port: int):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            result = s.connect_ex((ip, port))
            if result == 0:
                with lock:
                    discovered.append({
                        "ip": ip,
                        "port": port,
                        "type": "RTSP/HTTP",
                        "rtsp_url": f"rtsp://{ip}:{port}/h264" if port in [554, 8554] else f"http://{ip}:{port}/video"
                    })
        except Exception:
            pass
        finally:
            s.close()

    # Bounded thread pool executor
    with ThreadPoolExecutor(max_workers=50) as executor:
        for i in range(1, 255):
            ip = f"{subnet_prefix}.{i}"
            for port in ports:
                executor.submit(check_ip_port, ip, port)

    return discovered


def verify_rtsp_stream(url: str, timeout_sec: int = 3) -> bool:
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        return False
    ret, frame = cap.read()
    cap.release()
    return ret and frame is not None
