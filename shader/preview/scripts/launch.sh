#!/bin/bash
# Launch Valheim via Steam and return once QuietElements is up; game keeps running. Prints new mod/exception lines.
CL=$HOME/.local/share/Steam/logs/console-linux.txt
start=$(wc -l < "$CL"); echo $start > /tmp/qe-qe_logstart
steam -applaunch 892970 >/dev/null 2>&1 &
for i in $(seq 1 90); do sleep 2; tail -n +$start "$CL" | grep -q "overlay shader loaded" && break; done
sleep 12
tail -n +$start "$CL" | grep -i "quietelements\|claude\.\|exception" | cut -c1-200 | head -20
