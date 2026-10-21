#!/bin/bash
# rec.sh NAME ELEMENTS — fresh dummy with ELEMENTS, wait 3 s, record 36 frames at 12 fps into shots/gif_NAME
S="${QE_WORK:-$HOME/.cache/qe-preview}"
T=$HOME/.config/r2modmanPlus-local/Valheim/profiles/WhaDa/BepInEx/plugins/QETestbed
rm -rf $T/shots/gif_$1; before=$(grep -c "recorded gif_$1\$" $T/testbed.log)
$S/scripts/tb.sh "apply $2" "sleep 3" "record gif_$1 36 12" >/dev/null
for i in $(seq 1 60); do sleep 0.5; [ $(grep -c "recorded gif_$1\$" $T/testbed.log) -gt $before ] && break; done
echo "$1 $(ls $T/shots/gif_$1 | wc -l)"
