#!/usr/bin/env bash
# vboxsf_probe.sh — diagnose VirtualBox shared-folder access issues

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

USER=$(whoami)

echo "=== VirtualBox Shared Folder Probe ==="
echo "User: $USER"
echo ""

# 1. Check if user is in vboxsf group
echo -n "1. User in vboxsf group? "
if groups | grep -qw vboxsf; then
    echo -e "${GREEN}YES${NC}"
else
    echo -e "${RED}NO${NC} → Run: sudo usermod -a -G vboxsf $USER && logout/login"
fi

# 2. List /media/sf_* mounts
echo ""
echo "2. Shared folder mounts under /media/:"
MOUNTS=$(find /media -maxdepth 1 -type d -name 'sf_*' 2>/dev/null)
if [ -z "$MOUNTS" ]; then
    echo -e "${RED}None found${NC} → Check VirtualBox Shared Folders settings."
else
    for m in $MOUNTS; do
        echo "   $m"
        # Check readability
        if ls "$m" >/dev/null 2>&1; then
            echo -e "      ${GREEN}Readable${NC} ($(ls -1 "$m" | wc -l) items)"
        else
            echo -e "      ${RED}Permission denied${NC} → add user to vboxsf group"
        fi
    done
fi

# 3. Active vboxsf mounts from /proc/mounts
echo ""
echo "3. Active vboxsf mounts:"
grep vboxsf /proc/mounts | awk '{print "   " $2 " (" $3 ")"}' || echo "   None"

echo ""
echo "=== End of probe ==="
