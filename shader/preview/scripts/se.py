import sys, json, UnityPy
env = UnityPy.load(sys.argv[1])
want = {"Burning","Frost","Poison","Lightning","Spirit"}
for o in env.objects:
    if o.type.name != "MonoBehaviour": continue
    try: n = o.peek_name()
    except Exception: continue
    if n in want:
        try:
            t = o.read_typetree()
        except Exception as e:
            print(n, "typetree fail", e); continue
        out = {}
        for k,v in t.items():
            if isinstance(v, dict) and "m_effectPrefabs" in v:
                prefabs=[]
                for e in v["m_effectPrefabs"]:
                    p = e["m_prefab"]
                    name="?"
                    try:
                        ob = env.files and o.assets_file.files.get(p["m_PathID"]) if p["m_FileID"]==0 else None
                        name = ob.peek_name() if ob else f"ext{p}"
                    except Exception as ex: name=str(ex)
                    prefabs.append((name, p, e.get("m_attach"), e.get("m_scale"), e.get("m_enabled")))
                out[k]=prefabs
        print(n, json.dumps(out, default=str))
