#!/bin/sh
# lab.sh "<query>" out.png [virtual_ms]  — render the preview headless and crop to the two viewports
S="${QE_WORK:-$HOME/.cache/qe-preview}"
cd $S/page && timeout 120 chromium --headless=new --no-sandbox --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist --enable-logging=stderr --v=0 --window-size=1300,560 --virtual-time-budget=${3:-3500} --screenshot=$2 "file://$S/page/preview.html?lab=1&play=1&$1" 2>&1 | grep CONSOLE | head -3
