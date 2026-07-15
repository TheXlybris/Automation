"""
AgentGUI Core — Bidirectional Message Bus.

Profiles communicate with each other through a simple JSON file-based message queue.
Schema: {from, to, type, content, task_id, timestamp}

Message types:
  - result: task completion result (from agent to caller)
  - question: mid-task clarification request (from agent to caller/orchestrator)
  - status: progress update (from agent to caller)
  - system: system-level message (orchestrator to agent)
"""

import json
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

BUS_FILE = Path(__file__).parent.parent / "data" / "message_bus.json"
_lock = threading.RLock()

VALID_TYPES = {"result", "question", "status", "system"}
VALID_PROFILES = {"developer", "multimedia", "researcher", "wiki", "dreamer", "orchestrator", "default"}


def _ensure_file():
    if not BUS_FILE.exists():
        _write_bus({"messages": [], "last_update": datetime.now().isoformat()})


def _read_bus() -> dict:
    _ensure_file()
    with open(BUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_bus(data: dict):
    data["last_update"] = datetime.now().isoformat()
    BUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with open(BUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def send_message(from_profile: str, to_profile: str, content: str,
                 msg_type: str = "result", task_id: str = "") -> dict:
    """Send a message from one profile to another. Returns the created message."""
    if from_profile not in VALID_PROFILES:
        raise ValueError(f"Invalid from_profile: {from_profile}")
    if to_profile not in VALID_PROFILES:
        raise ValueError(f"Invalid to_profile: {to_profile}")
    if msg_type not in VALID_TYPES:
        raise ValueError(f"Invalid msg_type: {msg_type}. Valid: {VALID_TYPES}")
    if not content.strip():
        raise ValueError("content cannot be empty")

    bus = _read_bus()
    msg = {
        "id": f"msg_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(bus['messages'])}",
        "from": from_profile,
        "to": to_profile,
        "type": msg_type,
        "content": content,
        "task_id": task_id,
        "timestamp": datetime.now().isoformat(),
        "read": False,
    }
    bus["messages"].append(msg)
    _write_bus(bus)
    return msg


def get_inbox(profile: str, unread_only: bool = False) -> List[Dict]:
    """Get all messages addressed to a profile."""
    bus = _read_bus()
    msgs = [m for m in bus["messages"] if m["to"] == profile]
    if unread_only:
        msgs = [m for m in msgs if not m.get("read", False)]
    return msgs


def mark_read(msg_id: str) -> bool:
    """Mark a message as read."""
    bus = _read_bus()
    for m in bus["messages"]:
        if m["id"] == msg_id:
            m["read"] = True
            _write_bus(bus)
            return True
    return False


def clear_inbox(profile: str) -> int:
    """Remove all messages addressed to a profile. Returns count removed."""
    bus = _read_bus()
    before = len(bus["messages"])
    bus["messages"] = [m for m in bus["messages"] if m["to"] != profile]
    removed = before - len(bus["messages"])
    if removed > 0:
        _write_bus(bus)
    return removed


def get_all_messages() -> List[Dict]:
    """Get all messages in the bus (for debugging/admin)."""
    return _read_bus().get("messages", [])