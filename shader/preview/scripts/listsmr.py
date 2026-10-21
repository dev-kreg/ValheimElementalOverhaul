import sys, UnityPy
env = UnityPy.load(sys.argv[1])
want = {"Greydwarf","Troll","Wolf","Lox"}
for o in env.objects:
    if o.type.name != "GameObject": continue
    try: n = o.peek_name()
    except Exception: continue
    if n not in want: continue
    objs = o.assets_file.objects
    stack = [(o, "")]
    while stack:
        go, path = stack.pop(); g = go.read_typetree(); path = path + "/" + g["m_Name"]
        for c in g["m_Component"]:
            co = objs.get(c["component"]["m_PathID"])
            if not co: continue
            if co.type.name == "SkinnedMeshRenderer":
                t = co.read_typetree(); m = objs.get(t["m_Mesh"]["m_PathID"])
                mt = m.read_typetree() if m else {}
                texs = []
                for mp in t["m_Materials"]:
                    mo = objs.get(mp["m_PathID"])
                    if mo:
                        mm = mo.read_typetree()
                        for k, te in mm["m_SavedProperties"]["m_TexEnvs"]:
                            if k == "_MainTex" and te["m_Texture"]["m_PathID"]: 
                                to = objs.get(te["m_Texture"]["m_PathID"]); texs.append((mm["m_Name"], to.peek_name() if to else "ext", te["m_Texture"]["m_PathID"]))
                print(n, path, "mesh", mt.get("m_Name"), m.path_id if m else None, "verts", mt.get("m_VertexData",{}).get("m_VertexCount"), "readable", mt.get("m_IsReadable"), "active", g["m_IsActive"], "enabled", t["m_Enabled"], texs)
            if co.type.name == "Transform":
                for ch in co.read_typetree()["m_Children"]:
                    tr = objs.get(ch["m_PathID"])
                    if tr: stack.append((objs.get(tr.read_typetree()["m_GameObject"]["m_PathID"]), path))
