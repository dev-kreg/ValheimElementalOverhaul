import sys, json, os, UnityPy
env = UnityPy.load(sys.argv[1]); outdir = sys.argv[2]
ids = {"vfx_Burning":4378118342299409016,"vfx_Frost":1655877826925567196,"vfx_Poison":9081064533287565464,"fx_Lightning":564628846439144315,"vfx_UndeadBurn":4235182596766346521}
af = None
for o in env.objects:
    if o.path_id == ids["vfx_Burning"]: af = o.assets_file; break
objs = af.objects
def get(ptr):
    if ptr["m_FileID"]!=0 or ptr["m_PathID"]==0: return None
    return objs.get(ptr["m_PathID"])
textures = {}
def tex_of(mat_ptr):
    m = get(mat_ptr)
    if not m: return None
    t = m.read_typetree()
    sh = get(t["m_Shader"]); shn = sh.read().m_ParsedForm.m_Name if sh else None
    texs = {}
    for name, te in t["m_SavedProperties"]["m_TexEnvs"]:
        tx = get(te["m_Texture"])
        if tx:
            tn = tx.peek_name(); texs[name]=tn
            if tn not in textures:
                img = tx.read().image; img.save(os.path.join(outdir, tn+".png")); textures[tn]=img.size
    return {"name": t["m_Name"], "shader": shn, "tex": texs, "floats": dict(t["m_SavedProperties"]["m_Floats"]), "colors": dict(t["m_SavedProperties"]["m_Colors"]), "keywords": t.get("m_ValidKeywords") or t.get("m_ShaderKeywords")}
def walk(go_obj, depth=0):
    g = go_obj.read_typetree()
    node = {"name": g["m_Name"], "active": g["m_IsActive"], "comps": {}}
    tr = None
    for c in g["m_Component"]:
        co = get(c["component"])
        if not co: continue
        tn = co.type.name
        t = co.read_typetree()
        if tn == "Transform": tr = t; node["pos"]=t["m_LocalPosition"]; node["rot"]=t["m_LocalRotation"]; node["scale"]=t["m_LocalScale"]
        elif tn == "ParticleSystemRenderer":
            t["_materials"] = [tex_of(m) for m in t["m_Materials"]]
            node["comps"][tn]=t
        elif tn in ("ParticleSystem","Light"): node["comps"][tn]=t
        elif tn == "MonoBehaviour":
            sc = get(t["m_Script"]); node["comps"].setdefault("scripts",[]).append(sc.read().m_ClassName if sc else "?")
        else: node["comps"].setdefault("other",[]).append(tn)
    node["children"] = [walk(get(get(ch)["m_GameObject"] if False else None) ) for ch in []]
    kids=[]
    for ch in tr["m_Children"]:
        cto = get(ch).read_typetree()
        kids.append(walk(get(cto["m_GameObject"]), depth+1))
    node["children"]=kids
    return node
res = {k: walk(objs[v]) for k,v in ids.items()}
json.dump(res, open(os.path.join(outdir,"vfx.json"),"w"), default=lambda x: str(x), indent=1)
print("textures", textures)
