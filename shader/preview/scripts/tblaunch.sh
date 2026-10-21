#!/bin/bash
# (Re)start Valheim in testbed mode and wait until the test world is ready.
T=$HOME/.config/r2modmanPlus-local/Valheim/profiles/WhaDa/BepInEx/plugins/QETestbed
if pgrep -x valheim.x86_64 >/dev/null; then echo quit >> $T/testbed.cmd; for i in $(seq 1 40); do pgrep -x valheim.x86_64 >/dev/null || break; sleep 1; done; pkill -x valheim.x86_64; sleep 2; fi
: > $T/testbed.log
steam -applaunch 892970 -qetest >/dev/null 2>&1 &
for i in $(seq 1 90); do sleep 2; grep -q "ready" $T/testbed.log 2>/dev/null && break; done
cat $T/testbed.log
