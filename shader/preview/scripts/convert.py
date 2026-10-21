import json, sys, math
d = json.load(open(sys.argv[1]))
N = 24
def herm(keys, t):
    if not keys: return 0.0
    if t <= keys[0]["time"]: return keys[0]["value"]
    if t >= keys[-1]["time"]: return keys[-1]["value"]
    for a, b in zip(keys, keys[1:]):
        if a["time"] <= t <= b["time"]:
            dt = b["time"] - a["time"]
            if dt <= 0: return b["value"]
            s = (t - a["time"]) / dt
            m0 = a["outSlope"] * dt; m1 = b["inSlope"] * dt
            if math.isinf(m0) or math.isinf(m1): return a["value"]
            s2, s3 = s*s, s*s*s
            return (2*s3-3*s2+1)*a["value"] + (s3-2*s2+s)*m0 + (-2*s3+3*s2)*b["value"] + (s3-s2)*m1
def mm(c):
    """-> {k:'c', v:[min,max]} or {k:'curve', a:[...], b:[...]}"""
    st = c["minMaxState"]
    if st == 0: return {"k":"c","v":[c["scalar"],c["scalar"]]}
    if st == 3: return {"k":"c","v":[c["minScalar"],c["scalar"]]}
    smp = lambda cv: [round(herm(cv["m_Curve"], i/(N-1))*c["scalar"],4) for i in range(N)]
    if st == 1: s = smp(c["maxCurve"]); return {"k":"curve","a":s,"b":s}
    return {"k":"curve","a":smp(c["minCurve"]),"b":smp(c["maxCurve"])}
def grad(g, t):
    nc, na = g["m_NumColorKeys"], g["m_NumAlphaKeys"]
    def ev(times, vals, t, fixed):
        if t <= times[0]: return vals[0]
        for i in range(len(times)-1):
            if times[i] <= t <= times[i+1]:
                if fixed: return vals[i+1]
                s = (t-times[i])/max(1e-6, times[i+1]-times[i])
                return [x+(y-x)*s for x,y in zip(vals[i], vals[i+1])] if isinstance(vals[i], list) else vals[i]+(vals[i+1]-vals[i])*s
        return vals[-1]
    fixed = g["m_Mode"] == 1
    ct = [g[f"ctime{i}"]/65535 for i in range(nc)]; cv = [[g[f"key{i}"][c] for c in "rgb"] for i in range(nc)]
    at = [g[f"atime{i}"]/65535 for i in range(na)]; av = [g[f"key{i}"]["a"] for i in range(na)]
    return ev(ct, cv, t, fixed) + [ev(at, av, t, fixed)]
def col(c): return [c["r"],c["g"],c["b"],c["a"]]
def mg(g):
    st = g["minMaxState"]
    smp = lambda gr: [[round(x,3) for x in grad(gr, i/(N-1))] for i in range(N)]
    if st == 0: return {"k":"c","a":col(g["maxColor"]),"b":col(g["maxColor"])}
    if st == 2: return {"k":"c","a":col(g["minColor"]),"b":col(g["maxColor"])}
    if st == 1: s = smp(g["maxGradient"]); return {"k":"g","a":s,"b":s}
    return {"k":"g","a":smp(g["minGradient"]),"b":smp(g["maxGradient"])}  # random between two gradients
def matp(mat):
    """Approximate shading: rgb = tex*vcol*tint*lit + emis, alpha = tex.a*vcol.a*tint.a; blend add or alpha."""
    if not mat: return {"blend":"alpha","tint":[1,1,1,1],"emis":[0,0,0],"lit":1}
    f, c, sh = mat["floats"], mat["colors"], mat["shader"] or ""
    blend = "add" if int(f.get("_DstBlend", 10)) == 1 else "alpha"
    if mat["name"] in ("light_glow", "waystone_Trail"): blend = "add"  # shader not in this bundle; both are glow materials
    tint = col(c.get("_Color", {"r":1,"g":1,"b":1,"a":1}))
    emis = [c["_EmissionColor"][k] for k in "rgb"] if f.get("_EmissionEnabled") == 1.0 else [0,0,0]
    lit = 0.55 if ("Lit" in sh and "Unlit" not in sh) or f.get("_LightingEnabled") == 1.0 else 1
    if mat["name"] == "light_glow": tint[3] = c["_TintColor"]["a"]
    return {"blend":blend,"tint":tint,"emis":emis,"lit":lit}
def system(n, parent_scale):
    c = n["comps"]; ps = c["ParticleSystem"]; r = c.get("ParticleSystemRenderer", {})
    im, em, sh = ps["InitialModule"], ps["EmissionModule"], ps["ShapeModule"]
    mat = (r.get("_materials") or [None])[0]
    o = {"name": n["name"], "world": ps["moveWithTransform"]==1, "loop": bool(ps["looping"]), "dur": ps["lengthInSec"],
         "life": mm(im["startLifetime"]), "speed": mm(im["startSpeed"]), "size": mm(im["startSize"]),
         "color": mg(im["startColor"]), "grav": mm(im["gravityModifier"]), "max": im["maxNumParticles"],
         "rot0": mm(im["startRotation"]), "rate": mm(em["rateOverTime"]) if em["enabled"] else {"k":"c","v":[0,0]},
         "bursts": [[b["time"], mm(b["countCurve"])["v"][1] if b["countCurve"]["minMaxState"] in (0,3) else 0] for b in em.get("m_Bursts",[])] if em["enabled"] else [],
         "shape": {"type": sh["type"], "r": sh["radius"]["value"], "angle": sh["angle"], "scale": [sh["m_Scale"][k] for k in "xyz"], "pos": [sh["m_Position"][k] for k in "xyz"], "thick": sh["radiusThickness"]} if sh["enabled"] else None,
         "pos": [n["pos"][k] for k in "xyz"], "scale": [n["scale"][k]*parent_scale[i] for i,k in enumerate("xyz")],
         "render": r.get("m_RenderMode", 0), "lenScale": r.get("m_LengthScale", 1), "velScale": r.get("m_VelocityScale", 0),
         "maxScreen": r.get("m_MaxParticleSize", 0.5),
         "tex": (mat or {}).get("tex", {}).get("_MainTex"), **matp(mat), "scaleMode": ps["scalingMode"],
         "gray": (mat or {}).get("shader") == "Custom/Gradient Mapped Particle (Unlit)", "emisV": (mat or {}).get("shader") == "Custom/Particle (Unlit)",
         "rendOn": bool(r.get("m_Enabled", True))}
    if ps["ColorModule"]["enabled"]: o["col"] = mg(ps["ColorModule"]["gradient"])
    if ps["SizeModule"]["enabled"]: o["sol"] = mm(ps["SizeModule"]["curve"])
    v = ps["VelocityModule"]
    if v["enabled"]: o["vel"] = {"x": mm(v["x"]), "y": mm(v["y"]), "z": mm(v["z"]), "world": bool(v.get("inWorldSpace"))}
    f = ps["ForceModule"]
    if f["enabled"]: o["force"] = {"x": mm(f["x"]), "y": mm(f["y"]), "z": mm(f["z"])}
    nz = ps["NoiseModule"]
    if nz["enabled"]: o["noise"] = {"str": mm(nz["strength"]), "freq": nz["frequency"], "scroll": mm(nz["scrollSpeed"])}
    rm = ps["RotationModule"]
    if rm["enabled"]: o["rotv"] = mm(rm["curve"])
    uv = ps["UVModule"]
    if uv["enabled"]: o["uv"] = {"tx": uv["tilesX"], "ty": uv["tilesY"], "cycles": uv["cycles"], "start": mm(uv["startFrame"]), "fot": mm(uv["frameOverTime"])}
    t = ps["TrailModule"]
    if t["enabled"]:
        m2 = (r.get("_materials") or [None, None])[1] if len(r.get("_materials") or []) > 1 else None
        o["trail"] = {"life": mm(t["lifetime"]), "width": mm(t["widthOverTrail"]), "tex": (m2 or {}).get("tex",{}).get("_MainTex"), "col": mg(t["colorOverTrail"]), "inherit": bool(t.get("inheritParticleColor", 1))}
    return o
def walk(n, out, lights, scale=(1,1,1), active=True):
    active = active and n["active"]
    c = n["comps"]
    if active and "ParticleSystem" in c: out.append(system(n, scale))
    if active and "Light" in c:
        l = c["Light"]; lights.append({"color": col(l["m_Color"]), "int": l["m_Intensity"], "range": l["m_Range"], "pos": [n["pos"][k] for k in "xyz"]})
    for ch in n["children"]: walk(ch, out, lights, scale, active)
res = {}
for k, v in d.items():
    systems, lights = [], []
    walk(v, systems, lights)
    res[k] = {"systems": systems, "lights": lights}
json.dump(res, open(sys.argv[2], "w"), separators=(",", ":"))
for k, v in res.items():
    print(k, [(s["name"], s["blend"], s["tex"], s["max"], s["tint"], s["emis"], s["lit"]) for s in v["systems"]])
