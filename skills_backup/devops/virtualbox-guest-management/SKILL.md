---
name: virtualbox-guest-management
title: VirtualBox Guest Management
description: Manage shared folders, clipboard, display, and guest permissions in a VirtualBox VM (Linux guest, Windows host). Includes debugging permission issues on vboxsf mounts.
version: 1.0.0
tags: [virtualbox, vm, shared-folders, vboxsf, permissions, linux-guest]
---

# VirtualBox Guest Management

## When to Use

- The agent is running inside a VirtualBox VM (Linux guest) and needs to access shared folders from a Windows host.
- The user says they "shared a folder" in VirtualBox settings but the agent cannot access it.
- Permission denied (`Errno 13`) on paths under `/media/sf_*`.

## Shared Folders — How They Work

1. In VirtualBox Manager, the user sets a Shared Folder pointing to a host path (e.g. `C:\Users\X\Pictures\Screenshots`).
2. Inside the Linux guest, VirtualBox mounts it at `/media/sf_<FolderName>`.
   - **The prefix `sf_` is added automatically by VirtualBox.** The user often does not know this.
3. The mount is owned by `root:vboxsf` with mode `770`.
4. **Only members of the `vboxsf` group can read or write.**

## Quick Fix — Add User to vboxsf Group

```bash
sudo usermod -a -G vboxsf $(whoami)
```

Then **log out and log back in** (or reboot) for the new group membership to take effect.

## Temporary Workaround (Before Reboot)

If the user needs access immediately without logging out:

```bash
sg vboxsf -c "ls -la /media/sf_<FolderName>/"
```

Or copy files out:

```bash
sg vboxsf -c "cp /media/sf_<FolderName>/file.png /home/$(whoami)/tmp.png"
chown $(whoami):$(whoami) /home/$(whoami)/tmp.png
chmod 644 /home/$(whoami)/tmp.png
```

## Diagnostic Script

Run the verification script in this skill's `scripts/` directory:

```bash
bash ~/.hermes/skills/virtualbox-guest-management/scripts/vboxsf_probe.sh
```

It checks:
- Is the current user in the `vboxsf` group?
- Are there any `/media/sf_*` mounts?
- Can the user list them?

## Pitfalls

- **"Permission denied" on `/media/sf_*`** → User is not in `vboxsf` group. Do NOT try chmod/chown on the mount point; those require root and are not the right fix.
- **"No such file or directory" on `/media/sf_Foo`** → The folder name in VirtualBox might not match what the user thinks. List `/media/` to see the actual mount names.
- **Changes take effect only after logout/login.** `usermod` updates the system database but the running shell's group list is cached.
- **Do not put user custom scripts or tools inside `~/.hermes/hermes-agent/`.** That directory is a git repo and gets overwritten on `hermes update`. Always use `~/.hermes/skills/` or `~/.hermes/plugins/`.

## References

- `references/vboxsf-debug-session.md` — Full transcript of a real debugging session (screenshot access denied → group fix → copy workaround → permanent fix).
- `references/vbox-bridged-firewall-comfyui.md` — When Hermes (VM) needs REST API access to ComfyUI on Windows host: bridged adapter + Windows firewall rule with IP restriction, avoiding NAT/port-forwarding pitfalls.
