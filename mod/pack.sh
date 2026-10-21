#!/bin/sh
# Build the Thunderstore zip (`./pack.sh publish` also uploads it; needs TCLI_AUTH_TOKEN): package/ (manifest, README, CHANGELOG, icon) + the plugin and both shader bundles at the root.
set -e
cd "$(dirname "$0")"
dotnet build -c Release >/dev/null
VER=$(python3 -c "import json; print(json.load(open('package/manifest.json'))['version_number'])")
OUT="dist/ElementalOverhaul-$VER.zip"
mkdir -p dist && rm -f "$OUT"
SH=../shader/Build
python3 - "$OUT" package/manifest.json package/README.md package/CHANGELOG.md package/icon.png \
  bin/Release/ElementalOverhaul.dll $SH/linux/elementaloverlay_linux $SH/windows/elementaloverlay_windows <<'PY'
import sys, zipfile, os
with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED) as z:
    for f in sys.argv[2:]:
        z.write(f, os.path.basename(f))
PY
echo "$OUT"
[ "$1" = publish ] && ~/.dotnet/tools/tcli publish --file "$OUT"
