#!/usr/bin/env python3
# cfg.py Section.Key=value ...  — set values in the live QuietElements config (game reloads it)
import sys, re, os
p = os.path.expanduser("~/.config/r2modmanPlus-local/Valheim/profiles/WhaDa/BepInEx/config/ElementalOverhaul.cfg")
s = open(p).read()
for a in sys.argv[1:]:
    k, v = a.split("=", 1); sec, key = k.split(".")
    s2 = re.sub(r'(\[' + sec + r'\][\s\S]*?\n' + key + r' = )[^\n]*', lambda m: m.group(1) + v, s, count=1)
    if s2 == s and not re.search(r'\[' + sec + r'\][\s\S]*?\n' + key + ' = ' + re.escape(v) + r'\n', s): sys.exit("not found: " + a)
    s = s2
open(p, "w").write(s)
