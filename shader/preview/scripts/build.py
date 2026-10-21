import json, base64, sys, os
S = sys.argv[1]
data = open(os.path.join(S, "out/vfx_compact.json")).read()
json.loads(data.replace("Infinity", "1e999"))
tex = {}
for n in ["point", "spark 1", "flameball_big_flipbook", "blood", "wildfire01", "spark", "point2", "leaf_low"]:
    tex[n] = "data:image/png;base64," + base64.b64encode(open(os.path.join(S, f"out/{n}.png"), "rb").read()).decode()
t = open(os.path.join(S, "page/template.html")).read()
t = t.replace("__OVERLAYGEN__", open(os.path.expanduser("~/Projects/ValheimElementalShader/preview/overlay.gen.js")).read()).replace("__MESHES__", open(os.path.join(S, "out/meshes.json")).read()).replace("__DATA__", data).replace("__TEX__", json.dumps(tex))
open(os.path.join(S, "page/elemental-vfx.html"), "w").write(t)
print(len(t))
