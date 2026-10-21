import json, sys
d = json.load(open(sys.argv[1]))
def mm(c):
    s=c["minMaxState"]; 
    if s==0: return f"{c['scalar']:.3g}"
    if s==3: return f"[{c['minScalar']:.3g}..{c['scalar']:.3g}]"
    return f"curve(state{s})x{c['scalar']:.3g}"
def col(c): return "(%.2f,%.2f,%.2f,%.2f)"%(c["r"],c["g"],c["b"],c["a"])
def mg(g):
    s=g["minMaxState"]
    if s==0: return col(g["maxColor"])
    if s==2: return "rand "+col(g["minColor"])+"-"+col(g["maxColor"])
    return f"grad(state{s})"
def walk(n, path):
    p = path+"/"+n["name"]
    c = n["comps"]
    if "ParticleSystem" in c:
        ps=c["ParticleSystem"]; im=ps["InitialModule"]; em=ps["EmissionModule"]; sh=ps["ShapeModule"]
        r=c.get("ParticleSystemRenderer",{})
        mats=[(m or {}).get("name") for m in r.get("_materials",[])]
        texs=[(m or {}).get("tex") for m in r.get("_materials",[])]
        shd=[(m or {}).get("shader") for m in r.get("_materials",[])]
        print(f"  PS {p} active={n['active']} rendEnabled={r.get('m_Enabled')} mode={r.get('m_RenderMode')} loop={ps['looping']} dur={ps['lengthInSec']} space={ps.get('moveWithTransform')} scaleMode={ps.get('scalingMode')}")
        print(f"     life={mm(im['startLifetime'])} speed={mm(im['startSpeed'])} size={mm(im['startSize'])} color={mg(im['startColor'])} grav={mm(im['gravityModifier'])} max={im['maxNumParticles']}")
        bursts=[(b['time'],mm(b['countCurve'])) for b in em.get('m_Bursts',[])]
        print(f"     emit on={em['enabled']} rate={mm(em['rateOverTime'])} dist={mm(em['rateOverDistance'])} bursts={bursts}")
        print(f"     shape on={sh['enabled']} type={sh['type']} radius={sh.get('radius',{}).get('value') if isinstance(sh.get('radius'),dict) else sh.get('radius')} angle={sh.get('angle')} scale={sh.get('m_Scale')}")
        for mod in ["ColorModule","SizeModule","VelocityModule","UVModule","NoiseModule","RotationModule","ForceModule","TrailModule","LightsModule"]:
            if ps.get(mod,{}).get("enabled"): print(f"     +{mod}")
        print(f"     mats={mats} shader={shd} tex={texs}")
    if "Light" in c:
        l=c["Light"]; print(f"  LIGHT {p} col={col(l['m_Color'])} int={l['m_Intensity']} range={l['m_Range']} scripts={c.get('scripts')}")
    if c.get("scripts"): print(f"  scripts {p}: {c['scripts']}")
    for ch in n["children"]: walk(ch, p)
for k,v in d.items():
    print("=== ",k, "scale", v.get("scale")); walk(v,"")
