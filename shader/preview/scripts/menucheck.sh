#!/bin/bash
# Launch Valheim through Steam (r2modman WhaDa profile) to the main menu, collect mod lines from Steam's console log, close it.
CL=$HOME/.local/share/Steam/logs/console-linux.txt
start=$(wc -l < "$CL")
steam -applaunch 892970 >/dev/null 2>&1 &
for i in $(seq 1 90); do
  sleep 2
  tail -n +$start "$CL" | grep -q "QuietElements\|Zonesystem Start\|Steam manager" && [ $i -gt 15 ] && break
done
sleep 20
NEW=$(mktemp); tail -n +$start "$CL" > "$NEW"
echo "=== after ~$((i*2+20))s, new lines: $(wc -l < $NEW)"
grep -n -i "quietelements\|claude\.\|overlay shader" "$NEW" | cut -c1-220 | head -20
echo "=== exceptions"
grep -n -i -A4 "exception" "$NEW" | cut -c1-220 | head -40
echo "=== last lines"; tail -5 "$NEW" | cut -c1-200
cp "$NEW" /tmp/qe-valheim_session.log
