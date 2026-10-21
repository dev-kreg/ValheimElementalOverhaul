#!/bin/sh
# Generate the overlay sources, compile the shader bundles (Linux + Windows), and drop them next to ElementalOverhaul.dll.
set -e
python3 "$(dirname "$0")/tools/gen.py"
cd "$(dirname "$0")"
UNITY="$HOME/Unity/Hub/Editor/6000.0.75f1/Editor/Unity"
"$UNITY" -batchmode -quit -nographics -projectPath "$PWD" -executeMethod BuildBundle.Build -logFile build.log || { grep -E "error|Error|Shader" build.log | tail -30; exit 1; }
DEST="${PROFILE:-$HOME/.config/r2modmanPlus-local/Valheim/profiles/WhaDa}/BepInEx/plugins/ElementalOverhaul"
mkdir -p "$DEST"
cp Build/linux/elementaloverlay_linux Build/windows/elementaloverlay_windows "$DEST/"
echo "deployed elementaloverlay_linux + elementaloverlay_windows"
