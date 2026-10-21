#!/bin/bash
# tb.sh "cmd" ["cmd" ...]  — send testbed commands; for "shot NAME" waits for the file and writes a 1280px copy to /tmp/qe-tb_NAME.png
T=$HOME/.config/r2modmanPlus-local/Valheim/profiles/WhaDa/BepInEx/plugins/QETestbed
for c in "$@"; do
  case "$c" in
    sleep*) sleep ${c#sleep } ;;
    *) n=$(wc -l < $T/testbed.log); echo "$c" >> $T/testbed.cmd
       for i in $(seq 1 40); do sleep 0.25; [ $(wc -l < $T/testbed.log) -gt $n ] && break; done
       tail -n +$((n+1)) $T/testbed.log
       if [[ "$c" == shot* ]]; then f=$T/shots/${c#shot }.png; for i in $(seq 1 40); do sleep 0.25; [ -s $f ] && break; done; sleep 0.5
         python3 -c "from PIL import Image; im=Image.open('$f'); im.thumbnail((1280,720)); im.save('/tmp/qe-tb_${c#shot }.png')"; fi ;;
  esac
done
