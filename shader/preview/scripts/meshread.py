import sys, UnityPy
env = UnityPy.load(sys.argv[1])
want = {"Greydwarf","Troll","Boar","Wolf","Draugr","Lox","Seeker"}
for o in env.objects:
    if o.type.name != "GameObject": continue
    try: n = o.peek_name()
    except Exception: continue
    if n not in want: continue
    objs = o.assets_file.objects
    stack = [o]; seen = 0
    while stack:
        g = stack.pop().read_typetree()
        for c in g["m_Component"]:
            co = objs.get(c["component"]["m_PathID"])
            if not co: continue
            if co.type.name == "SkinnedMeshRenderer":
                t = co.read_typetree(); m = objs.get(t["m_Mesh"]["m_PathID"])
                if m:
                    mt = m.read_typetree(); print(n, mt["m_Name"], "readable", mt.get("m_IsReadable"), "verts", mt.get("m_VertexData",{}).get("m_VertexCount"), "submeshes", len(mt["m_SubMeshes"]), "mats", len(t["m_Materials"])); seen += 1
            if co.type.name == "Transform":
                for ch in co.read_typetree()["m_Children"]:
                    tr = objs.get(ch["m_PathID"])
                    if tr: stack.append(objs.get(tr.read_typetree()["m_GameObject"]["m_PathID"]))
        if seen >= 2: break
