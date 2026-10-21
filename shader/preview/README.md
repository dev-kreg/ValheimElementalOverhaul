# Preview and dev scripts

A browser replay of the effects, used to iterate on the look without launching the game. It needs data extracted from **your own** Valheim install. That data is never committed.

1. Extract with UnityPy (in a venv) from `valheim_Data/StreamingAssets/SoftRef/Bundles/c4210710`:
   - `dump.py` and then `convert.py`: the vanilla effect prefabs and textures, into `$QE_WORK/out/`.
   - `meshes.py`: the creature meshes, into `$QE_WORK/out/meshes.json`.
2. Copy `template.html` into `$QE_WORK/page/`, then run `build.py $QE_WORK` to produce `$QE_WORK/page/elemental-vfx.html`. The shared shader comes from `../overlay.gen.js`, which `shader/tools/gen.py` writes.
3. `lab.sh` and `sheet.py` render headless Chromium screenshots of the preview. URL parameters such as `?els=fire,frost&target=Troll&Fire.Glow=1.5&age=8` set up a scene.

In-game scripts that drive QETestbed (see the root README):
- `tblaunch.sh`: launch the game in test mode.
- `tb.sh`: send commands.
- `rec.sh`: record a clip.
- `tour.sh` and `variants.sh`: screenshot grids.
- `cfg.py Section.Key=value`: change the live config.

`QE_WORK` defaults to `~/.cache/qe-preview`. The preview approximates Valheim's own particle shaders, so fire tongues in particular look different from the game. In-game captures are the reference.
