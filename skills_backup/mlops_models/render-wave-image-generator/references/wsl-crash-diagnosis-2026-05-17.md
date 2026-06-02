# WSL Crash Dump Analysis — Session 2026-05-17

## Incident Summary

- **Time:** ~23:37 local time
- **Symptom:** WSL terminal window closed unexpectedly mid-session; Hermes session lost
- **User activity:** Actively chatting with Hermes agent (not idle)
- **Root cause:** Chrome running under WSLg triggered dxg GPU driver crash, killing WSL2 VM

## Evidence Timeline

```
22:44:31  Gateway PID 374 exits with SystemExit:75 (TERM FAIL)
22:50:01  Gateway PID 355 exits with SystemExit:75 (TERM FAIL)
~23:37    WSL crash — Chrome dxg driver failure
23:47:53  WSL2 boots fresh (dmesg shows kernel boot)
23:48:10  systemd starts, journal rotated ("uncleanly shut down")
23:50:01  Hermes gateway auto-restarted by systemd
23:52:08  Current Hermes session begins
```

## Crash Dump Details

**File:** `C:\Users\Fil_B\AppData\Local\Temp\wsl-crashes\wsl-crash-1779057466-5862-_opt_google_chrome_chrome-5.dmp`
- **Size:** 398 MB
- **Process:** `/opt/google/chrome/chrome` (renderer/gpu process)

## Root Cause Chain

Chrome → Mesa/Wayland → WSLg → dxg (DirectX on Hyper-V) → Windows GPU driver. Repeated `dxgkio_query_adapter_info` IOCTL failures (visible in dmesg) destabilize the Hyper-V virtual GPU. Driver crash cascades to WSL2 VM kernel panic → VM killed by Hyper-V supervisor.

## Diagnostic Commands

```bash
# Check for WSL crash dumps
ls -lt /mnt/c/Users/Fil_B/AppData/Local/Temp/wsl-crashes/*.dmp

# Check systemd events from past 30 minutes
journalctl --since "30 minutes ago" --no-pager | tail -30

# Check kernel boot time (reveals crash vs idle timeout)
dmesg -T | head -5

# Check Hermes gateway recent exits
cat ~/.hermes/logs/gateway-exit-diag.log | tail -5
```

## Prevention Options

1. **Disable GPU in Chrome (WSL):** `google-chrome --disable-gpu`
2. **Run Chrome on Windows host** — no WSLg/dxg involvement
3. **Check crash dumps before resuming** — confirms root cause for user

## Model Viability Note

This crash occurred during investigation of local model viability. With qwen3.5:35b requiring 18GB RAM (exceeds 16GB available), and gemma4:26b producing empty responses at 36s/turn, **Ollama Cloud (kimi-k2.6) remains the only viable option** for agent models on this hardware.
