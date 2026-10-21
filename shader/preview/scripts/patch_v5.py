import sys, re
p = sys.argv[1]; s = open(p).read()
def rep(o, n, c=1):
    global s
    assert s.count(o) == c, (o[:90], s.count(o))
    s = s.replace(o, n)

# 1. shared overlay source + schema come from the project's generator
a = s.index("const OVERLAY = `"); b = s.index("`;", a) + 2
s = s[:a] + "__OVERLAYGEN__\nconst OVERLAY = OVERLAY_GLSL;" + s[b:]

# 2. mesh shader: engine uniforms, flat normals; plus a shell program
rep("""uniform vec3 ambient, sunDir, sunCol, fogCol; uniform float fogD;
${OVERLAY}
void main(){""", """uniform vec3 ambient, sunDir, sunCol, fogCol; uniform float fogD; uniform float _ElemScale;
${OVERLAY}
void main(){""")
rep("  if (cutoff >= 0. && tx.a < cutoff) discard; // alpha-cutout fur and hair, like the game material",
    "  if (_ElemCutoff >= 0. && tx.a < _ElemCutoff) discard; // alpha-cutout fur and hair, like the game material")
rep("""  vec3 oMul, oAdd; overlay(vP*elemScale, n, v, length(fwidth(vP*elemScale)), oMul, oAdd); c = c*oMul + oAdd;""",
    """  vec3 nf = normalize(cross(dFdy(vP), dFdx(vP))); if (dot(nf, v) < 0.) nf = -nf;   // flat normal for faceted ice
  vec3 sp = vP*_ElemScale;
  vec3 oMul, oAdd; overlay(sp, n, nf, v, length(fwidth(sp)), oMul, oAdd); c = c*oMul + oAdd;""")
rep("const VS_PART = `#version 300 es", """const VS_SHELL = `#version 300 es
in vec3 aP; in vec3 aN; in vec2 aT; out vec3 vP; out vec3 vN; out vec2 vT; out vec3 vW;
uniform vec3 camPos, camR, camU, camF; uniform float tanH, aspect, projA, projB, _ShellH, _GlobalShellHeight, _ElemScale;
void main(){ vP = aP; vN = aN; vT = aT;
  vec3 w = aP + normalize(aN) * (.004 + _ShellH * _GlobalShellHeight / max(_ElemScale, .05)); vW = w;
  vec3 d = w - camPos; float z = dot(d, camF);
  gl_Position = vec4(dot(d, camR)/(tanH*aspect), dot(d, camU)/tanH, projA*z + projB, z); }`;
const FS_SHELL = `#version 300 es
precision highp float; in vec3 vP; in vec3 vN; in vec2 vT; in vec3 vW; out vec4 o;
uniform sampler2D tex; uniform vec3 camPos; uniform float _ShellH, _ElemScale;
${OVERLAY}
void main(){
  if (_ElemCutoff >= 0. && texture(tex, vT).a < _ElemCutoff) discard;
  vec3 v = normalize(camPos - vW); vec3 n = normalize(vN); if(dot(n, v) < 0.) n = -n;
  vec3 sp = vP*_ElemScale; vec3 col; float al;
  shell(sp, n, v, length(fwidth(sp)), _ShellH, col, al);
  o = vec4(col, al); }`;
const VS_PART = `#version 300 es""")
rep("this.pMesh = this.prog(VS_MESH, FS_MESH); this.meshes = {};", "this.pMesh = this.prog(VS_MESH, FS_MESH); this.pShell = this.prog(VS_SHELL, FS_SHELL); this.meshes = {};")

# 3. uniforms: engine + every schema param, then shell layers after the mesh
rep("""    gl.uniform4fv(pm.u.elemA, ov.slice(0, 4)); gl.uniform1f(pm.u.elemB, ov[4]); gl.uniform1f(pm.u.uTime, time); gl.uniform1f(pm.u.elemLight, L.litLevel); gl.uniform1f(pm.u.cutoff, CREATURE_MESH[scene.mesh].cut); gl.uniform1f(pm.u.elemScale, 1 / Math.sqrt(CREATURES[scene.mesh].h / 1.8));""",
    """    const engine = (pr) => {
      gl.uniform4fv(pr.u._ElemA, ov.slice(0, 4)); gl.uniform1f(pr.u._ElemB, ov[4]); gl.uniform1f(pr.u.uTime, time);
      gl.uniform4fv(pr.u._ElemAge, ELEM_KEYS.slice(0, 4).map((k) => elemAge(k))); gl.uniform1f(pr.u._ElemLight, L.litLevel);
      gl.uniform1f(pr.u._ElemCutoff, CREATURE_MESH[scene.mesh].cut); gl.uniform3fv(pr.u._ElemSunDir, L.sunDir);
      gl.uniform1f(pr.u._ElemScale, 1 / Math.sqrt(CREATURES[scene.mesh].h / 1.8)); setParams(gl, pr);
    };
    engine(pm);""")
rep("""    gl.bindVertexArray(me.vao); gl.drawElements(gl.TRIANGLES, me.count, gl.UNSIGNED_SHORT, 0); gl.bindVertexArray(null);
    // particles""", """    gl.bindVertexArray(me.vao); gl.drawElements(gl.TRIANGLES, me.count, gl.UNSIGNED_SHORT, 0);
    // layers floating above the skin (premultiplied), same mesh pushed out along its normals
    const shells = this.isMod && scene.overlay ? Math.round(PARAMS.Global.ShellCount) : 0;
    if (shells > 0) {
      const sh = this.pShell; gl.useProgram(sh); this.camUniforms(sh, cam, scene.cap);
      gl.uniform1f(sh.u.projA, cam.projA); gl.uniform1f(sh.u.projB, cam.projB); engine(sh);
      gl.uniform1i(sh.u.tex, 0); gl.depthMask(false); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      for (let k = 1; k <= shells; k++) { gl.uniform1f(sh.u._ShellH, k / shells); gl.drawElements(gl.TRIANGLES, me.count, gl.UNSIGNED_SHORT, 0); }
      gl.disable(gl.BLEND);
    }
    gl.bindVertexArray(null);
    // particles""")
# the mesh VAO's attribute locations come from pMesh; make the shell program use the same ones
rep("    p.a = {}; const na = gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES);", "    for (const [i, nm] of [[0, \"aP\"], [1, \"aN\"], [2, \"aT\"]]) gl.bindAttribLocation(p, i, nm); gl.linkProgram(p);\n    p.a = {}; const na = gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES);")

# 4. params state, ages, lightning gate from params
rep("const state = {", r'''// ---------- tunables (schema from params.json via tools/gen.py) ----------
const ELEM_KEYS = ["fire", "frost", "poison", "lightning", "spirit"];
const PARAMS = {}; const PARAM_DEFAULTS = {};
const lin2srgb = (x) => (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
const srgb2lin = (x) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
const toHex = (c) => c.map((x) => Math.round(clamp01(lin2srgb(x)) * 255).toString(16).padStart(2, "0")).join("").toUpperCase();
const fromHex = (h) => [0, 2, 4].map((i) => srgb2lin(parseInt(h.slice(i, i + 2), 16) / 255));
for (const sec of PARAM_SCHEMA) { PARAMS[sec.name] = {}; PARAM_DEFAULTS[sec.name] = {}; for (const [n, t, d] of sec.params) { PARAMS[sec.name][n] = Array.isArray(d) ? d.slice() : d; PARAM_DEFAULTS[sec.name][n] = d; } }
try { const saved = JSON.parse(localStorage.getItem("qe-params") || "{}"); for (const s in saved) for (const n in saved[s]) if (PARAMS[s] && n in PARAMS[s]) PARAMS[s][n] = saved[s][n]; } catch (e) {}
const uniformCache = new WeakMap();
function setParams(gl, prog) {
  for (const sec of PARAM_SCHEMA) for (const [n, t] of sec.params) {
    if (t === "p") continue;
    const loc = prog.u["_" + sec.name + n]; if (!loc) continue;
    const v = PARAMS[sec.name][n];
    if (t === "c") gl.uniform3fv(loc, v); else gl.uniform1f(loc, v);
  }
}
const onSince = {};
function elemAge(k) { return state.ageOverride != null ? state.ageOverride : Math.max(0, time - (onSince[k] ?? 0)); }

const state = {''')
rep("function shaderBurst(t) { return (h3(Math.floor(t * 3), 1.3, 2.1) >= 0.5 ? 1 : 0) * (h3(Math.floor(t * 15), 0.37, 0.71) >= 0.25 ? 1 : 0); }",
    "function shaderBurst(t) { const L = PARAMS.Lightning; return (h3(Math.floor(t * L.BurstRate), 1.3, 2.1) >= 1 - L.BurstChance ? 1 : 0) * (h3(Math.floor(t * L.FlickerRate), 0.37, 0.71) >= 0.25 ? 1 : 0); }")
rep("      if (l.flash) flick *= 0.6 + 1.6 * shaderBurst(time);", "      if (l.flash) flick *= Math.max(0, 1 + PARAMS.Lightning.LightFlash * (1.6 * shaderBurst(time) - 0.4));")
# lab overrides: ?Fire.Glow=2.5 ; ?age=6
rep('  if (q.has("lab")) document.documentElement.classList.add("lab");', '''  if (q.has("age")) state.ageOverride = +q.get("age");
  for (const [k, v] of q) { const [sec, n] = k.split("."); if (n && PARAMS[sec] && n in PARAMS[sec]) PARAMS[sec][n] = Array.isArray(PARAMS[sec][n]) ? fromHex(v) : +v; }
  if (q.has("lab")) document.documentElement.classList.add("lab");''')

# 5. particles take their numbers from the params
rep("    const s = Object.assign({}, sys, { rate: C(sys.density * area * budget) });",
    """    const T = TUNED[sys.name] ? TUNED[sys.name]() : {};
    const G = PARAMS.Global, size = T.size != null ? T.size * G.ParticleSize : null;
    const s = Object.assign({}, sys, { rate: C((T.density ?? sys.density) * G.ParticleDensity * area * budget) },
      size != null ? { size: C(size * 0.7, size * 1.3) } : {}, T.vel ? { vel: Object.assign({}, sys.vel, T.vel) } : {});""")
rep("const OVERHAUL_LABEL = {", '''// which params drive which particle system (mirrors ElementalBody.cs)
const TUNED = {
  tongues: () => ({ density: PARAMS.Fire.TongueDensity, size: PARAMS.Fire.TongueSize, vel: { y: C(PARAMS.Fire.TongueRise * 0.65, PARAMS.Fire.TongueRise * 1.3) } }),
  embers: () => ({ density: PARAMS.Fire.EmberDensity, size: PARAMS.Fire.EmberSize }),
  flakes: () => ({ density: PARAMS.Frost.FlakeDensity, size: PARAMS.Frost.FlakeSize, vel: { y: C(-PARAMS.Frost.FlakeFall * 1.4, -PARAMS.Frost.FlakeFall * 0.6) } }),
  drips: () => ({ density: PARAMS.Poison.DripDensity, size: PARAMS.Poison.DripSize }),
  sparks: () => ({ density: PARAMS.Lightning.SparkDensity, size: PARAMS.Lightning.SparkSize }),
  wisps: () => ({ density: PARAMS.Spirit.WispDensity, size: 0.02, vel: { y: C(PARAMS.Spirit.WispRise * 0.6, PARAMS.Spirit.WispRise * 1.4) } }),
};
const OVERHAUL_LABEL = {''')
open(p, "w").write(s); print("ok")
