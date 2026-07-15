#!/usr/bin/env python3
"""
AgentGUI Profile Runner — wiki
Reads task file, loads SOUL.md, invokes hermes chat with the correct model.
"""

import sys
import os
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

# --- Auto-injected Global Logger ---
try:
    from core.logger_config import setup_global_logging
    setup_global_logging(str(Path(__file__).parent.parent / "logs"))
except Exception as e:
    print(f"Failed to initialize logger: {e}")
# -------------------------------------

BASE_DIR = Path(os.environ.get("AGENTUI_DIR", "/media/sf_AI_Ecosystem/10_Projects/02_AgentGUI"))
DATA_DIR = BASE_DIR / "data"
PROFILE_NAME = "wiki"
SOUL_FILE = Path.home() / ".hermes" / "profiles" / PROFILE_NAME / "SOUL.md"

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 run_wiki.py <agent_id>")
        sys.exit(1)
    
    agent_id = sys.argv[1]
    task_file = DATA_DIR / f"{agent_id}_task.json"
    
    if not task_file.exists():
        print(f"[{agent_id}] Task file nao encontrado: {task_file}")
        # Write done flag with error
        done_flag = DATA_DIR / f"{agent_id}_done.flag"
        done_flag.write_text("1")
        sys.exit(1)
    
    task_data = json.loads(task_file.read_text())
    goal = task_data.get("goal", "")
    model = task_data.get("model")
    
    print(f"[{agent_id}] A ler tarefa e SOUL.md...")
    print(f"[{agent_id}] Profile: {PROFILE_NAME}")
    print(f"[{agent_id}] Model: {model or 'default'}")
    print(f"[{agent_id}] Task: {goal[:100]}...")
    
    # Load SOUL.md if it exists
    soul_content = ""
    if SOUL_FILE.exists():
        soul_content = SOUL_FILE.read_text(encoding="utf-8")
    
    # Load skills config
    skills_config_path = Path.home() / ".hermes" / "profiles" / PROFILE_NAME / "skills_config.json"
    enabled_skills = []
    if skills_config_path.exists():
        try:
            sc = json.loads(skills_config_path.read_text())
            enabled_skills = sc.get("enabled", [])
        except Exception:
            pass
    
    # Build prompt
    prompt = f"""You are operating as the {PROFILE_NAME} profile in the AgentGUI ecosystem.

"""
    if soul_content:
        prompt += f"=== SOUL.md (persona) ===\n{soul_content}\n\n"
    
    prompt += f"=== TASK ===\n{goal}\n"
    
    print(f"[{agent_id}] A construir prompt...")
    print(f"[{agent_id}] A invocar hermes chat...")
    
    # Ensure hermes is findable even if PATH doesn't include ~/.local/bin
    hermes_bin = str(Path.home() / ".local" / "bin" / "hermes")
    if not Path(hermes_bin).exists():
        hermes_bin = "hermes"  # fallback to PATH lookup

    # Build hermes chat command
    cmd = [hermes_bin, "chat", "-q", prompt, "-Q", "--ignore-rules", "--source", "tool"]
    
    # Add model if specified
    if model:
        cmd.extend(["-m", model])
    
    # Add skills if any
    if enabled_skills:
        cmd.extend(["-s", ",".join(enabled_skills)])
    
    # Run hermes chat
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            stdin=subprocess.DEVNULL
        )
        
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        
        print(f"[{agent_id}] Hermes chat completed with exit code {result.returncode}")
        print(f"[{agent_id}] Output length: {len(output)} chars")
        
        # Write result.json for loop closure (FASE 2)
        duration = time.time() - start_time
        result_data = {
            "agent_id": agent_id,
            "profile": PROFILE_NAME,
            "exit_code": result.returncode,
            "output": output,
            "duration": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        result_file = DATA_DIR / f"{agent_id}_result.json"
        result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))

        # FASE 4: Send result via message bus
        try:
            sys.path.insert(0, str(BASE_DIR))
            from core.message_bus import send_message
            caller = task_data.get("caller_profile", "orchestrator")
            send_message(
                from_profile=PROFILE_NAME,
                to_profile=caller,
                content=output[:2000] if output else f"[exit {result.returncode}]",
                msg_type="result",
                task_id=agent_id,
            )
        except Exception as mb_e:
            print(f"[{agent_id}] message_bus send failed: {mb_e}")
        
        # Write done flag
        done_flag = DATA_DIR / f"{agent_id}_done.flag"
        done_flag.write_text(str(result.returncode))
        
        if result.returncode == 0:
            print(f"[{agent_id}] Tarefa concluida")
        else:
            print(f"[{agent_id}] Tarefa terminou com erro (exit {result.returncode})")
        
        # Print output for tmux capture
        if output:
            print(output[:5000])
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"[{agent_id}] Timeout apos {duration:.0f}s")
        result_data = {
            "agent_id": agent_id,
            "profile": PROFILE_NAME,
            "exit_code": 1,
            "output": f"[Timeout after {duration:.0f}s]",
            "duration": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        result_file = DATA_DIR / f"{agent_id}_result.json"
        result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))
        done_flag = DATA_DIR / f"{agent_id}_done.flag"
        done_flag.write_text("1")
    except Exception as e:
        duration = time.time() - start_time
        print(f"[{agent_id}] Erro: {e}")
        result_data = {
            "agent_id": agent_id,
            "profile": PROFILE_NAME,
            "exit_code": 1,
            "output": f"[Error: {str(e)}]",
            "duration": round(duration, 2),
            "timestamp": datetime.now().isoformat()
        }
        result_file = DATA_DIR / f"{agent_id}_result.json"
        result_file.write_text(json.dumps(result_data, indent=2, ensure_ascii=False))
        done_flag = DATA_DIR / f"{agent_id}_done.flag"
        done_flag.write_text("1")

if __name__ == "__main__":
    main()
