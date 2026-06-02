# VirtualBox vboxsf Permission Debug Session

**Date:** 2026-05-19  
**Host:** Windows 11  
**Guest:** Ubuntu 22.04 in VirtualBox  
**Trigger:** User shared `C:\Users\Fil_B\Pictures\Screenshots` via VirtualBox Shared Folders. Agent could not read the image.

## Problem

User said: "eu já partilhei a C:\Users\Fil_B\Pictures\Screenshots contigo no oracle virutalbox. so se falta algum comando depois disso."

Agent initially could not see the image because it is in a Linux VM, not on the Windows host.

## Diagnosis Steps

1. Checked `/media/` for `sf_*` mounts — found `/media/sf_Screenshots`
2. Checked `mount | grep vboxsf` — confirmed `Screenshots on /media/sf_Screenshots type vboxsf`
3. `ls -la /media/sf_Screenshots/` → **Permission denied**
4. `id` showed user `xlybris` is NOT in group `vboxsf`

## Root Cause

VirtualBox mounts shared folders as `root:vboxsf` with mode `770`. Only members of the `vboxsf` group can access them. Adding a shared folder in VirtualBox Manager does NOT automatically add the guest user to `vboxsf`.

## Fix Applied

```bash
sudo usermod -a -G vboxsf xlybris
```

Then, for immediate access without logout:

```bash
sg vboxsf -c "cp '/media/sf_Screenshots/Captura de ecrã 2026-05-19 013603.png' /home/xlybris/screenshot_temp.png"
chown xlybris:xlybris /home/xlybris/screenshot_temp.png
chmod 644 /home/xlybris/screenshot_temp.png
```

After this, `vision_analyze` worked.

## Permanent Fix

Logout and login again (or reboot) so the new group membership is picked up by the shell.

## Key Takeaway

When a user says "I shared a folder in VirtualBox", the agent should:
1. Check `/media/sf_*` for the mount
2. Verify user is in `vboxsf` group
3. If not, run `sudo usermod -a -G vboxsf $(whoami)` and warn that logout/login is needed
4. Use `sg vboxsf -c "command"` as a temporary workaround
