import sys, json, base64, io, struct, UnityPy, numpy as np
from UnityPy.helpers.MeshHelper import MeshHandler
env = UnityPy.load(sys.argv[1]); outp = sys.argv[2]
PICK = {"Greydwarf": ["Cube", "Cube.001"], "Troll": ["Body", "Hair"], "Wolf": ["M"], "Lox": ["Body", "Furr1"]}
def quat_mat(q):
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)], [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)], [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
def trs(t):
    M = np.eye(4); s = t["m_LocalScale"]; p = t["m_LocalPosition"]
    M[:3, :3] = quat_mat(t["m_LocalRotation"]) @ np.diag([s["x"], s["y"], s["z"]]); M[:3, 3] = [p["x"], p["y"], p["z"]]
    return M
out = {}
done = set()
for o in env.objects:
    if o.type.name != "GameObject": continue
    try: n = o.peek_name()
    except Exception: continue
    if n not in PICK or n in done: continue
    objs = o.assets_file.objects
    parts = []
    stack = [(o, np.eye(4), True)]
    while stack:
        go, M, top = stack.pop(); g = go.read_typetree()
        comps = {objs.get(c["component"]["m_PathID"]).type.name: objs.get(c["component"]["m_PathID"]) for c in g["m_Component"] if objs.get(c["component"]["m_PathID"])}
        tr = comps["Transform"].read_typetree()
        W = np.eye(4) if top else M @ trs(tr)  # root at origin
        if "SkinnedMeshRenderer" in comps and g["m_Name"] in PICK[n] and g["m_IsActive"]:
            t = comps["SkinnedMeshRenderer"].read_typetree()
            mesh = objs[t["m_Mesh"]["m_PathID"]].read()
            mh = MeshHandler(mesh); mh.process()
            V = np.array(mh.m_Vertices, dtype=np.float64).reshape(-1, 3)
            N = np.array(mh.m_Normals, dtype=np.float64).reshape(-1, 3)
            UV = np.array(mh.m_UV0, dtype=np.float64).reshape(-1, 2)
            tris = [i for sub in mh.get_triangles() for tri in sub for i in tri]
            V4 = np.c_[V, np.ones(len(V))] @ W.T
            Nw = N @ np.linalg.inv(W[:3, :3]).T; Nw /= np.linalg.norm(Nw, axis=1, keepdims=True) + 1e-9
            texid, cut = None, -1.0
            for mp in t["m_Materials"]:
                mo = objs.get(mp["m_PathID"])
                if mo:
                    mt = mo.read_typetree()
                    for k, te in mt["m_SavedProperties"]["m_TexEnvs"]:
                        if k == "_MainTex" and te["m_Texture"]["m_PathID"]: texid = te["m_Texture"]["m_PathID"]
                    kw = " ".join(str(mt.get(x, "")) for x in ("m_ValidKeywords", "m_InvalidKeywords", "m_ShaderKeywords"))
                    if "_ALPHATEST_ON" in kw: cut = dict(mt["m_SavedProperties"]["m_Floats"]).get("_Cutoff", 0.5)
            parts.append((g["m_Name"], V4[:, :3], Nw, UV, tris, texid, cut))
        if g["m_Name"] == "Visual" or top or True:
            for ch in tr["m_Children"]:
                cto = objs.get(ch["m_PathID"])
                if cto: stack.append((objs.get(cto.read_typetree()["m_GameObject"]["m_PathID"]), W, False))
    if len(parts) < len(PICK[n]): continue
    done.add(n)
    allV = np.vstack([p[1] for p in parts])
    print(n, "bounds min", allV.min(0).round(2), "max", allV.max(0).round(2), [(p[0], len(p[1]), len(p[4]) // 3) for p in parts])
    texid, cut = parts[0][5], max(p[6] for p in parts)
    img = objs[texid].read().image; img.thumbnail((512, 512))
    buf = io.BytesIO()
    if cut >= 0: img.convert("RGBA").save(buf, "PNG"); mime = "png"   # keep alpha for cutout fur
    else: img.convert("RGB").save(buf, "JPEG", quality=82); mime = "jpeg"
    print(n, "cutoff", cut)
    pos, nor, uv, idx = [], [], [], []
    for name, V, Nw, UV, tris, _, _c in parts:
        base = len(pos) // 3
        pos += V.astype(np.float32).ravel().tolist(); nor += Nw.astype(np.float32).ravel().tolist(); uv += UV.astype(np.float32).ravel().tolist()
        idx += [base + i for i in tris]
    b64 = lambda arr, fmt: base64.b64encode(np.array(arr, dtype=fmt).tobytes()).decode()
    # exported normals don't match the geometry for some meshes: rebuild smooth, area-weighted normals
    P = np.array(pos, dtype=np.float64).reshape(-1, 3); I = np.array(idx).reshape(-1, 3)
    fn = np.cross(P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]]); Nn = np.zeros_like(P)
    for k in range(3): np.add.at(Nn, I[:, k], fn)
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-12
    Nn *= np.sign(((P - P.mean(0)) * Nn).sum(1).mean())
    nor = Nn.ravel().tolist()
    out[n] = {"pos": b64(pos, np.float32), "nor": b64(nor, np.float32), "uv": b64(uv, np.float32), "idx": b64(idx, np.uint16 if len(pos) // 3 < 65536 else np.uint32),
              "tex": f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode(), "cut": cut, "min": allV.min(0).tolist(), "max": allV.max(0).tolist()}
json.dump(out, open(outp, "w"))
