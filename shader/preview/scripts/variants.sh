#!/bin/bash
# variants.sh OUT.png ELEMENTS "label|Sec.Key=v Sec.Key=v" ...  — each variant: set cfg, apply on fresh dummy, shot; tiles 3 across
S="${QE_WORK:-$HOME/.cache/qe-preview}"
out=$1; els=$2; shift 2; names=()
for it in "$@"; do l=${it%%|*}; kv=${it#*|}; n=v_$(echo "$l" | tr -c 'a-zA-Z0-9' '_'); names+=("$n|$l")
  [ -n "$kv" ] && python3 $S/scripts/cfg.py $kv; sleep 1.5
  $S/scripts/tb.sh "apply $els" "sleep ${WAIT:-5}" "shot $n" | grep -i fail; done
python3 - "$out" "${names[@]}" <<'PY'
import sys
from PIL import Image, ImageDraw
out=sys.argv[1]; tiles=[]
for it in sys.argv[2:]:
    n,l=it.split("|",1); im=Image.open(f'/tmp/qe-tb_{n}.png'); w,h=im.size; im=im.crop((w//4,h//12,w*3//4,h)).resize((440,440))
    d=ImageDraw.Draw(im); d.rectangle((0,0,440,18),fill=(0,0,0)); d.text((6,3),l,fill=(255,220,150)); tiles.append(im)
rows=(len(tiles)+2)//3; o=Image.new('RGB',(1320,440*rows))
for i,t in enumerate(tiles): o.paste(t,((i%3)*440,(i//3)*440))
o.save(out)
PY
