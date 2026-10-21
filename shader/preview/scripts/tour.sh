#!/bin/bash
# tour.sh OUT.png "label|elements" ...  — apply each set on fresh dummies, screenshot, tile 3 across
S="${QE_WORK:-$HOME/.cache/qe-preview}"
out=$1; shift; names=()
for it in "$@"; do l=${it%%|*}; e=${it#*|}; n=t_$(echo "$l" | tr -c 'a-zA-Z0-9' '_'); names+=("$n|$l")
  $S/scripts/tb.sh "apply $e" "sleep ${WAIT:-5}" "shot $n" | grep -i fail; done
python3 - "$out" "${names[@]}" <<'PY'
import sys
from PIL import Image, ImageDraw
out=sys.argv[1]; tiles=[]
for it in sys.argv[2:]:
    n,l=it.split("|",1); im=Image.open(f'/tmp/qe-tb_{n}.png'); w,h=im.size; im=im.crop((w//4,h//12,w*3//4,h)).resize((440,440))
    d=ImageDraw.Draw(im); d.rectangle((0,0,440,18),fill=(0,0,0)); d.text((6,3),l,fill=(255,220,150)); tiles.append(im)
cols=3; rows=(len(tiles)+2)//3; o=Image.new('RGB',(440*cols,440*rows))
for i,t in enumerate(tiles): o.paste(t,((i%cols)*440,(i//cols)*440))
o.save(out)
PY
