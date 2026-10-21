import sys, UnityPy
env = UnityPy.load(sys.argv[1])
want = {"Greydwarf","Troll","Boar","Deer","Skeleton","Draugr","Wolf","Lox","Seeker","Fuling","Neck","Abomination","Gjall","Charred_Melee","Serpent"}
for o in env.objects:
    if o.type.name != "GameObject": continue
    try: n = o.peek_name()
    except Exception: continue
    if n not in want: continue
    g = o.read_typetree(); objs = o.assets_file.objects
    for c in g["m_Component"]:
        co = objs.get(c["component"]["m_PathID"])
        if co and co.type.name == "CapsuleCollider":
            t = co.read_typetree(); print(n, "radius", t["m_Radius"], "height", t["m_Height"], "center", t["m_Center"])
        if co and co.type.name == "Transform":
            s = co.read_typetree()["m_LocalScale"]
            if abs(s["x"]-1) > 1e-3: print(n, "scale", s)
