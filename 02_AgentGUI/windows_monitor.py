#!/usr/bin/env python3
"""
Windows Resource Monitor — Sends system stats to AgentGUI server on VM.
Runs on Windows host (192.168.0.187). Sends data every 2 seconds via HTTP POST.

Usage: python windows_monitor.py
Or: start via .bat for background execution
"""

import time
import json
import urllib.request
import urllib.error

# Detect if we're on Windows
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: psutil not installed. Install: pip install psutil")

# Configuration
VM_SERVER = "http://192.168.0.188:5020"
ENDPOINT = f"{VM_SERVER}/api/resources/windows"
INTERVAL = 2  # seconds

def get_windows_resources():
    if not PSUTIL_AVAILABLE:
        return None
    
    import psutil
    cpu_perc = psutil.cpu_percent(interval=None)
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    disk_c = psutil.disk_usage('C:/')
    
    # Try D: drive
    disk_d = None
    try:
        disk_d = psutil.disk_usage('D:/')
    except Exception:
        pass
    
    # Try GPU info via nvidia-smi or WMI
    gpu_info = None
    try:
        import subprocess
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(', ')
            if len(parts) == 4:
                gpu_info = {
                    'name': parts[0],
                    'vram_used_mb': int(parts[1]),
                    'vram_total_mb': int(parts[2]),
                    'gpu_percent': int(parts[3])
                }
    except Exception:
        pass
    
    disks = {
        'c': {
            'used_gb': round(disk_c.used / (1024**3), 1),
            'total_gb': round(disk_c.total / (1024**3), 1),
            'percent': round(disk_c.percent, 1)
        }
    }
    if disk_d:
        disks['d'] = {
            'used_gb': round(disk_d.used / (1024**3), 1),
            'total_gb': round(disk_d.total / (1024**3), 1),
            'percent': round(disk_d.percent, 1)
        }
    
    resources = {
        'source': 'windows',
        'cpu': {
            'percent': round(cpu_perc, 1),
            'cores': psutil.cpu_count(logical=True),
            'freq_mhz': round(cpu_freq.current, 0) if cpu_freq else 0
        },
        'ram': {
            'used_gb': round(ram.used / (1024**3), 1),
            'total_gb': round(ram.total / (1024**3), 1),
            'percent': ram.percent
        },
        'disks': disks,
        'gpu': gpu_info,
        'hostname': 'Windows-Host'
    }
    return resources

def send_data(data):
    try:
        payload = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            ENDPOINT,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Failed to send data: {e}")
        return False

def main():
    print("=" * 50)
    print(" Windows Resource Monitor")
    print(f" Sending to: {VM_SERVER}")
    print(f" Interval: {INTERVAL}s")
    print("=" * 50)
    
    if not PSUTIL_AVAILABLE:
        print("ERROR: psutil not installed.")
        print("Install: pip install psutil")
        return 1
    
    print("Monitor started. Press Ctrl+C to stop.")
    print()
    
    try:
        while True:
            data = get_windows_resources()
            if data:
                success = send_data(data)
                status = "✓" if success else "✗"
                print(f"[{status}] CPU: {data['cpu']['percent']:5.1f}% | "
                      f"RAM: {data['ram']['percent']:5.1f}% | "
                      f"Disk C: {data['disks']['c']['percent']:5.1f}% | "
                      f"Disk D: {data['disks'].get('d', {}).get('percent', 0):5.1f}% | "
                      f"GPU: {'OK' if data['gpu'] else 'N/A'}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
    return 0

if __name__ == "__main__":
    exit(main())
