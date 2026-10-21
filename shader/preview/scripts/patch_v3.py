import sys
p = sys.argv[1]; s = open(p).read()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:90], s.count(old))
    s = s.replace(old, new)

# ---------- 1. overlay shader v2: separate channels, multiply + add, chunky texel grid ----------
a = s.index("const OVERLAY = `"); b = s.index("`;", a) + 2
s = s[:a] + r'''const OVERLAY = `
// --- port of ElementalOverlay.shader v2 (keep constants in sync) ---
uniform vec4 elemA; uniform float elemB, uTime, elemLight;
float h3(vec3 p){ p = fract(p*.3183099+.1); p *= 17.; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }
float vn3(vec3 x){ vec3 i=floor(x), f=fract(x); f=f*f*(3.-2.*f);
  return mix(mix(mix(h3(i),h3(i+vec3(1,0,0)),f.x), mix(h3(i+vec3(0,1,0)),h3(i+vec3(1,1,0)),f.x),f.y),
             mix(mix(h3(i+vec3(0,0,1)),h3(i+vec3(1,0,1)),f.x), mix(h3(i+vec3(0,1,1)),h3(i+vec3(1,1,1)),f.x),f.y), f.z); }
float fbm3(vec3 p){ return vn3(p)*.5 + vn3(p*2.03)*.3 + vn3(p*4.01)*.2; }
// distance to nearest and second-nearest cell point; F2-F1 gives crystal / vein edges
vec2 vor(vec3 x){ vec3 i=floor(x), f=fract(x); float d1=8., d2=8.;
  for(int z=-1;z<=1;z++) for(int y=-1;y<=1;y++) for(int k=-1;k<=1;k++){
    vec3 g=vec3(float(k),float(y),float(z)); vec3 o=vec3(h3(i+g),h3(i+g+17.1),h3(i+g+31.7));
    vec3 r=g+o-f; float d=dot(r,r); if(d<d1){ d2=d1; d1=d; } else if(d<d2) d2=d; }
  return vec2(sqrt(d1), sqrt(d2)); }
// snap to a coarse texel grid so patterns match Valheim's chunky low-res textures
vec3 texel(vec3 p, float perMetre){ return (floor(p*perMetre)+.5)/perMetre; }
vec3 fireRamp(float t){
  vec3 c = mix(vec3(0.), vec3(.55,.06,.01), smoothstep(0.,.3,t));
  c = mix(c, vec3(1.9,.5,.08), smoothstep(.3,.65,t));
  return mix(c, vec3(2.6,1.7,.7), smoothstep(.65,1.,t)); }
void overlay(vec3 p, vec3 n, vec3 v, out vec3 mul, out vec3 add){
  float fres = 1.-clamp(dot(n,v),0.,1.); float t = uTime;
  mul = vec3(1.); add = vec3(0.); vec3 addL = vec3(0.);
  float fire = elemA.x, frost = elemA.y, poison = elemA.z, lightning = elemA.w, spirit = elemB;
  float active = step(.01,fire)+step(.01,frost)+step(.01,poison)+step(.01,lightning)+step(.01,spirit);
  float dim = inversesqrt(max(active,1.)); // stacked elements share the brightness budget
  if(fire > .001){
    vec3 q = texel(p, 20.);
    float n1 = fbm3(q*2.2 + vec3(0.,-t*.8,0.));
    float n2 = fbm3(q*4.6 + vec3(0.,-t*1.6,0.) + n1*1.5);       // two scales, two speeds: no visible tiling
    float crack = 1.-abs(2.*vn3(q*3.4 + vec3(0.,-t*.45,0.) + n1*1.2)-1.);
    crack = smoothstep(.8,.96,crack)*smoothstep(.35,.55,n2);   // glowing seams, broken up
    float lick = smoothstep(.55,.9, n2 + fres*.55) * smoothstep(.35,.85,fres) * smoothstep(-.4,.4,n.y+.2);
    float flick = .82 + .18*sin(t*11. + n1*7.);
    add += fireRamp(clamp(crack*.85 + lick, 0., 1.)) * fire * flick * dim;
    mul *= mix(vec3(1.), vec3(.38,.32,.28), fire*.75*smoothstep(.45,.62,n1)*(1.-crack)); // soot patches
  }
  if(frost > .001){
    vec3 q = texel(p, 24.);
    float cover = smoothstep(.45,.62, fbm3(q*3.1) + n.y*.28) * frost;
    vec2 c = vor(q*9.); float edge = 1.-smoothstep(0.,.07, c.y-c.x);
    mul *= mix(vec3(1.), vec3(.74,.86,1.05), frost*.85);          // whole body goes cold
    mul *= mix(vec3(1.), vec3(1.5,1.62,1.8), cover*.7);            // crust brightens with scene light
    add += vec3(.5,.68,.85)*elemLight*cover*(.06 + edge*.3)*dim;
    add += vec3(.4,.62,.9)*pow(fres,1.6)*frost*(.12 + .25*elemLight)*dim; // soft icy rim
    float cell = h3(floor(p*30.)); float tw = step(.993, cell)*(.5+.5*sin(t*2.5 + cell*60.));
    add += vec3(1.4,1.7,2.1)*tw*cover;                              // still glints, slow twinkle
  }
  if(poison > .001){
    vec3 q = texel(p, 20.);
    vec2 c = vor(q*5.); float vein = (1.-smoothstep(0.,.06, c.y-c.x)) * smoothstep(.4,.62, fbm3(q*2.));
    float pulse = pow(.5+.5*sin(t*2.4 - p.y*5.), 3.);              // pulses travel up the body
    mul *= mix(vec3(1.), vec3(.8,.97,.66), poison*.75);
    add += vec3(.3,.75,.06)*vein*(.18 + 1.1*pulse)*poison*dim;
    add += vec3(.2,.42,.04)*pow(fres,2.)*poison*(.1+.3*elemLight)*dim; // wet sheen
  }
  if(lightning > .001){
    float s = floor(t*15.);
    float burst = step(.5, h3(vec3(floor(t*3.),1.3,2.1)));         // ~3 bursts a second, half of them fire
    float on = burst * step(.25, h3(vec3(s,.37,.71)));
    vec3 q = texel(p, 28.);
    float f1 = vn3(q*2.6 + s*3.1), f2 = vn3(q*6.2 + s*1.7);
    float arc = 1.-smoothstep(.014,.04, abs(f1-.5));
    arc += .6*(1.-smoothstep(.01,.026, abs(f2-.5)))*smoothstep(.42,.5,f1);   // short branches near main arcs
    addL += vec3(.55,1.5,2.4)*arc*on*1.8*lightning;
    addL += vec3(.25,.65,1.2)*pow(fres,2.)*lightning*(.08 + on*.7);
  }
  if(spirit > .001){
    float wisp = smoothstep(.55,.85, fbm3(texel(p,18.)*2.4 + vec3(0.,-t*.9,0.))) * smoothstep(.2,.8,fres);
    mul *= mix(vec3(1.), vec3(.72,.9,.88), spirit*.5);
    add += vec3(.22,1.05,.85)*(pow(fres,2.2)*.55 + wisp*1.1)*spirit*dim;
  }
  add += addL;
}
`;''' + s[b:]

rep("  vec4 ov = overlay(vP, n, v); c = c*(1.-ov.a) + ov.rgb;", "  vec3 oMul, oAdd; overlay(vP, n, v, oMul, oAdd); c = c*oMul + oAdd;")
rep("    gl.uniform4fv(pm.u.elemA, ov.slice(0, 4)); gl.uniform1f(pm.u.elemB, ov[4]); gl.uniform1f(pm.u.uTime, time);",
    "    gl.uniform4fv(pm.u.elemA, ov.slice(0, 4)); gl.uniform1f(pm.u.elemB, ov[4]); gl.uniform1f(pm.u.uTime, time); gl.uniform1f(pm.u.elemLight, L.litLevel);")

# ---------- 2. overhaul particle systems built from the game's own textures ----------
rep("const state = {", r'''// ---------- overhaul particle design (my systems, same schema as the extracted game data) ----------
const C = (a, b = a) => ({ k: "c", v: [a, b] });
function ramp(stops, n) { const out = []; for (let i = 0; i < 24; i++) { const t = i / 23; let j = 0; while (j < stops.length - 2 && t > stops[j + 1][0]) j++; const A = stops[j], B = stops[j + 1], f = clamp01((t - A[0]) / ((B[0] - A[0]) || 1)); out.push(n === 1 ? lerp(A[1], B[1], f) : [1, 2, 3, 4].map((k) => lerp(A[k], B[k], f))); } return out; }
const G = (stops) => { const a = ramp(stops, 4); return { k: "g", a, b: a }; };
const CV = (stops) => { const a = ramp(stops, 1); return { k: "curve", a, b: a }; };
const sysDef = (o) => Object.assign({ world: true, loop: true, dur: 5, life: C(1), speed: C(0), size: C(0.1), color: { k: "c", a: [1, 1, 1, 1], b: [1, 1, 1, 1] }, grav: C(0), max: 300, rot0: C(0), rate: C(0), bursts: [], shape: null, pos: [0, 0, 0], scale: [1, 1, 1], render: 0, lenScale: 1, velScale: 0, maxScreen: 0.5, tex: "point", blend: "add", tint: [1, 1, 1, 1], emis: [0, 0, 0], lit: 1, scaleMode: 2, gray: false, emisV: false, rendOn: true }, o);
// density = particles per second per square metre of body surface; ny = allowed normal.y range for spawn points
const OVERHAUL = {
  fire: { light: { col: [1, 0.6, 0.28], int: 2 }, systems: [
    sysDef({ name: "tongues", density: 5, ny: [-0.15, 1], tex: "flameball_big_flipbook", gray: true, life: C(0.45, 0.8), size: C(0.2, 0.36), rot0: C(-0.4, 0.4),
      vel: { x: C(-0.1, 0.1), y: C(0.8, 1.5), z: C(-0.1, 0.1), world: true }, uv: { tx: 8, ty: 8, cycles: 1, start: C(0, 0.9999), fot: CV([[0, 0], [1, 1]]) },
      col: G([[0, 1, 0.95, 0.7, 0], [0.12, 1, 0.78, 0.35, 1], [0.5, 1, 0.42, 0.1, 0.75], [1, 0.55, 0.1, 0.02, 0]]), sol: CV([[0, 0.55], [0.3, 1], [1, 0.35]]) }),
    sysDef({ name: "embers", density: 1.6, ny: [-0.2, 1], tex: "spark 1", emisV: true, emis: [4, 2.27, 0.09], life: C(1, 2), size: C(0.025, 0.05),
      color: { k: "c", a: [1, 0.77, 0, 1], b: [1, 1, 1, 1] }, vel: { x: C(0), y: C(0.6, 1.3), z: C(0), world: true }, noise: { str: C(0.6), freq: 1.2, scroll: C(0.1) },
      col: G([[0, 1, 0.9, 0.5, 0], [0.1, 1, 0.8, 0.4, 1], [1, 1, 0.3, 0.05, 0]]), sol: CV([[0, 1], [1, 0]]) }),
  ] },
  frost: { light: { col: [0.6, 0.8, 1], int: 0.5 }, systems: [
    sysDef({ name: "flakes", density: 2.2, ny: [-1, 1], tex: "point", blend: "alpha", lit: 0.55, life: C(1.2, 2.2), size: C(0.025, 0.045),
      color: { k: "c", a: [0.85, 0.93, 1, 0.9], b: [1, 1, 1, 0.9] }, vel: { x: C(-0.05, 0.05), y: C(-0.45, -0.2), z: C(-0.05, 0.05), world: true }, noise: { str: C(0.2), freq: 2, scroll: C(0.05) },
      col: G([[0, 1, 1, 1, 0], [0.15, 1, 1, 1, 1], [0.8, 1, 1, 1, 1], [1, 1, 1, 1, 0]]) }),
  ] },
  poison: { light: { col: [0.5, 0.9, 0.2], int: 0.4 }, systems: [
    sysDef({ name: "drips", density: 1.3, ny: [-1, 0.1], tex: "point", blend: "alpha", lit: 0.55, emis: [0.05, 0.12, 0.01], life: C(0.6, 0.95), size: C(0.03, 0.05),
      render: 1, lenScale: 2.4, color: { k: "c", a: [0.42, 0.8, 0.08, 0.95], b: [0.55, 0.9, 0.15, 0.95] }, grav: C(0.55),
      col: G([[0, 1, 1, 1, 0], [0.1, 1, 1, 1, 1], [0.85, 1, 1, 1, 1], [1, 1, 1, 1, 0]]) }),
  ] },
  lightning: { light: { col: [0.4, 0.78, 1], int: 1.2, flash: true }, systems: [
    sysDef({ name: "sparks", density: 2.5, ny: [-1, 1], tex: "spark", blend: "alpha", tint: [0, 0, 0, 1], emis: [0, 1.5, 2.12], life: C(0.06, 0.12), size: C(0.16, 0.3), rot0: C(0, 6.28) }),
  ] },
  spirit: { light: { col: [0.5, 1, 0.65], int: 1.2 }, systems: [
    sysDef({ name: "wisps", density: 1.2, ny: [-0.3, 1], tex: "spark 1", emisV: true, emis: [4, 2.27, 0.09], render: 5, life: C(1, 2), size: C(0.02),
      color: { k: "c", a: [0.01, 0.78, 0.65, 1], b: [0.17, 0.88, 0.79, 1] }, vel: { x: C(0), y: C(0.35, 0.8), z: C(0), world: true }, noise: { str: C(0.5), freq: 1, scroll: C(0.1) },
      trail: { life: C(0.35), width: CV([[0, 1], [1, 0]]), tex: "point2", col: G([[0, 1, 1, 1, 1], [1, 1, 1, 1, 0]]) },
      col: G([[0, 1, 0.9, 0.5, 0], [0.1, 1, 0.85, 0.47, 1], [1, 0.9, 0.3, 0.3, 0]]) }),
  ] },
};
const OVERHAUL_LABEL = { tongues: "Flame tongues on the body (game fire flipbook)", embers: "Rising embers", flakes: "Falling frost flakes", drips: "Poison drips", sparks: "Surface spark flashes", wisps: "Rising spirit wisps" };

const state = {''')

# lab params for local test renders (?els=fire,frost&target=Troll&mode=quiet&yaw=3.1&dist=4&tod=day)
rep('playing: !matchMedia("(prefers-reduced-motion: reduce)").matches };', '''playing: !matchMedia("(prefers-reduced-motion: reduce)").matches, yaw: 0.27 };
{
  const q = new URLSearchParams(location.search);
  if (q.has("els")) { const on = q.get("els").split(","); for (const k in state.on) state.on[k] = on.includes(k); }
  for (const k of ["target", "mode", "tod"]) if (q.has(k)) state[k] = q.get(k);
  for (const k of ["yaw", "dist"]) if (q.has(k)) state[k] = +q.get(k);
}''')

# emitter: area-weighted spawn with normal filter
rep("      const M = this.surf, k = M.pickTri(R()), i0 = M.idx[k * 3] * 3, i1 = M.idx[k * 3 + 1] * 3, i2 = M.idx[k * 3 + 2] * 3;\n      let u = R(), w = R(); if (u + w > 1) { u = 1 - u; w = 1 - w; }\n      wp = [0, 1, 2].map((j) => M.pos[i0 + j] * (1 - u - w) + M.pos[i1 + j] * u + M.pos[i2 + j] * w);\n      d = norm([0, 1, 2].map((j) => M.nor[i0 + j] * (1 - u - w) + M.nor[i1 + j] * u + M.nor[i2 + j] * w));",
    "      const M = this.surf;\n      for (let tries = 0; tries < 8; tries++) {\n        const k = M.pickTri(R()), i0 = M.idx[k * 3] * 3, i1 = M.idx[k * 3 + 1] * 3, i2 = M.idx[k * 3 + 2] * 3;\n        let u = R(), w = R(); if (u + w > 1) { u = 1 - u; w = 1 - w; }\n        wp = [0, 1, 2].map((j) => M.pos[i0 + j] * (1 - u - w) + M.pos[i1 + j] * u + M.pos[i2 + j] * w);\n        d = norm([0, 1, 2].map((j) => M.nor[i0 + j] * (1 - u - w) + M.nor[i1 + j] * u + M.nor[i2 + j] * w));\n        if (!s.ny || (d[1] >= s.ny[0] && d[1] <= s.ny[1])) break;\n      }")
rep("  CREATURE_MESH[name] = { pos, nor: dec(m.nor, Float32Array), uv: dec(m.uv, Float32Array), idx, tex: m.tex, pickTri };",
    "  CREATURE_MESH[name] = { pos, nor: dec(m.nor, Float32Array), uv: dec(m.uv, Float32Array), idx, tex: m.tex, pickTri, area: acc };")

# build overhaul emitters + single light
rep("function lightsFor(S, center, mod) {", '''function buildOverhaul(seed) {
  const R = rng(seed), M = CREATURE_MESH[state.target], keys = Object.keys(OVERHAUL).filter((k) => state.on[k]);
  const budget = 1 / Math.sqrt(Math.max(keys.length, 1)); // stacked elements share the particle budget
  // ponytail: T-pose meshes overstate surface area a little; cap so Troll/Lox don't flood
  const area = Math.min(M.area, 14);
  const list = [];
  for (const k of keys) for (const sys of OVERHAUL[k].systems) {
    const s = Object.assign({}, sys, { rate: C(sys.density * area * budget) });
    list.push(new Emitter(s, 1, null, R, [0, 0, 0], M));
  }
  return list;
}
function overhaulLight(center) {
  const keys = Object.keys(OVERHAUL).filter((k) => state.on[k]);
  if (!keys.length) return [];
  let w = 0; const col = [0, 0, 0]; let int = 0, flash = false;
  for (const k of keys) { const l = OVERHAUL[k].light; col.forEach((_, i) => col[i] += l.col[i] * l.int); w += l.int; int = Math.max(int, l.int); flash = flash || !!l.flash; }
  const c = CREATURES[state.target];
  return [{ pos: [0, c.h * 0.6, 0], col: col.map((x) => toLin(x / w)), int: int * state.mod.light * 2, range: Math.max(4, c.h * 2.2), seed: 1.7, flash }];
}
function lightsFor(S, center, mod) {''')
rep("    const em = buildEffects(scene.S, scene.center, mod, 1234, mod && state.mode === \"overhaul\" ? CREATURE_MESH[state.target] : null);",
    "    const over = mod && state.mode === \"overhaul\";\n    const em = over ? buildOverhaul(1234) : buildEffects(scene.S, scene.center, mod, 1234, null);")
rep("    return { em, lights: lightsFor(scene.S, scene.center, mod) };", "    return { em, lights: over ? overhaulLight(scene.center) : lightsFor(scene.S, scene.center, mod) };")

# lightning light flashes in sync with the shader's bursts
rep("      const flick = 0.82 + 0.18 * (Math.sin(time * 9.1 + l.seed) * 0.5 + Math.sin(time * 23.7 + l.seed * 2) * 0.5);",
    "      let flick = 0.82 + 0.18 * (Math.sin(time * 9.1 + l.seed) * 0.5 + Math.sin(time * 23.7 + l.seed * 2) * 0.5);\n      if (l.flash) flick *= 0.6 + 1.6 * shaderBurst(time);")
rep("// ---------- WebGL2 renderer ----------", '''// same hash as the shader, so the light flashes with the arcs
function h3(x, y, z) { x = x * 0.3183099 + 0.1; y = y * 0.3183099 + 0.1; z = z * 0.3183099 + 0.1; x = (x - Math.floor(x)) * 17; y = (y - Math.floor(y)) * 17; z = (z - Math.floor(z)) * 17; const v = x * y * z * (x + y + z); return v - Math.floor(v); }
function shaderBurst(t) { return (h3(Math.floor(t * 3), 1.3, 2.1) >= 0.5 ? 1 : 0) * (h3(Math.floor(t * 15), 0.37, 0.71) >= 0.25 ? 1 : 0); }

// ---------- WebGL2 renderer ----------''')

# camera yaw
rep("  const camPos = [D * 0.28, center[1] + 0.35 + D * 0.12, -D];", "  const camPos = [Math.sin(state.yaw) * D, center[1] + 0.35 + D * 0.12, -Math.cos(state.yaw) * D];")

# ---------- 3. particle screen fill (overdraw proxy) ----------
rep("    let count = 0;\n    for (const em of emitters) {", "    let count = 0; this.fill = 0;\n    for (const em of emitters) {")
rep("    return { count, lsum };", "    return { count, lsum, fill: this.fill };")
rep("    const push = (x, y, u, v, c, z) => {", "    const self = this;\n    const push = (x, y, u, v, c, z) => {")
rep("      const p00 = [cx - ax - bx, cy - ay - by],", "      self.fill += Math.abs(ax * by - ay * bx); // quad area in NDC / 4 = fraction of the screen\n      const p00 = [cx - ax - bx, cy - ay - by],")
rep('''    document.getElementById(i ? "cntB" : "cntA").textContent = r.count;''', '''    document.getElementById(i ? "cntB" : "cntA").textContent = r.count;
    document.getElementById(i ? "fillB" : "fillA").textContent = (r.fill * 100).toFixed(0) + "%";''')
rep('<figcaption><span><b id="cntA">0</b> particles on screen</span>', '<figcaption><span><b id="cntA">0</b> particles · <b id="fillA">0%</b> screen fill</span>')
rep('<figcaption><span><b id="cntB">0</b> particles on screen</span>', '<figcaption><span><b id="cntB">0</b> particles · <b id="fillB">0%</b> screen fill</span>')

# mode copy + slider visibility
rep('<button type="button" data-v="overhaul" aria-pressed="true">Shrink + body overhaul</button>', '<button type="button" data-v="overhaul" aria-pressed="true">Overhaul</button>')
rep('''    document.getElementById("tagB").textContent = state.mode === "overhaul" ? "QuietElements · body overhaul (preview)" : "QuietElements";
    rebuild("b");''', '''    syncMode(); rebuild("b");''')
rep('<span class="tag mod" id="tagB">QuietElements · body overhaul (preview)</span>', '<span class="tag mod" id="tagB">Overhaul</span>')
rep("function bindUI() {", '''function syncMode() {
  const over = state.mode === "overhaul";
  document.querySelectorAll("#mode button").forEach((x) => x.setAttribute("aria-pressed", x.dataset.v === state.mode));
  document.getElementById("tagB").textContent = over ? "Overhaul" : "QuietElements (shrink only)";
  for (const id of ["mSize", "mEmit"]) document.getElementById(id).closest(".slider").hidden = over;
}
function bindUI() {''')
rep("bindUI();\n", "bindUI(); syncMode();\n")
open(p, "w").write(s); print("ok")
