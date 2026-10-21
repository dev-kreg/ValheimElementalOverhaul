import sys
p = sys.argv[1]; s = open(p).read()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:80], s.count(old))
    s = s.replace(old, new)

# A: lift overlay GLSL out of the scene shader into its own block for the mesh shader
a = s.index("uniform vec4 elemA; uniform float elemB, uTime;")
b = s.index("float hash(vec2 p){ return fract(sin(")
overlay = s[a:b]
s = s[:a] + s[b:]
rep("const FS_SCENE = `#version 300 es", "const OVERLAY = `\n" + overlay + "`;\nconst FS_SCENE = `#version 300 es")

# B: the creature is now a rasterized mesh; the scene pass draws only sky and ground
rep("  float tc = capIntersect(ro, rd, capA, capB, capR);\n", "  float tc = -1.;\n")
rep("    vec4 ov = overlay(p, n, -rd); col = col*(1.-ov.a) + ov.rgb; }", "  }")

# C/D: particles get real depth and are occluded by the depth buffer instead of the analytic capsule
rep("in vec2 aPos; in vec2 aUV; in vec4 aCol; in float aZ;", "in vec2 aPos; in vec2 aUV; in vec4 aCol; in float aZ; uniform float projA, projB;")
rep("gl_Position=vec4(aPos,0.,1.); }`;", "gl_Position=vec4(aPos*aZ, projA*aZ+projB, aZ); }`;")
rep("  float tc = capIntersect(camPos, rd, capA, capB, capR);\n  if(tc > 0. && tc*fz < vZ) discard;\n", "")

# G: mesh shaders
rep("const VS_PART = `#version 300 es", """const VS_MESH = `#version 300 es
in vec3 aP; in vec3 aN; in vec2 aT; out vec3 vP; out vec3 vN; out vec2 vT;
uniform vec3 camPos, camR, camU, camF; uniform float tanH, aspect, projA, projB;
void main(){ vP = aP; vN = aN; vT = aT; vec3 d = aP - camPos; float z = dot(d, camF);
  gl_Position = vec4(dot(d, camR)/(tanH*aspect), dot(d, camU)/tanH, projA*z + projB, z); }`;
const FS_MESH = `#version 300 es
precision highp float; in vec3 vP; in vec3 vN; in vec2 vT; out vec4 o;
uniform sampler2D tex; uniform vec3 camPos;
uniform vec3 Lpos[6]; uniform vec3 Lcol[6]; uniform float Lrange[6]; uniform int Ln;
uniform vec3 ambient, sunDir, sunCol, fogCol; uniform float fogD;
${OVERLAY}
void main(){
  vec3 v = normalize(camPos - vP); vec3 n = normalize(vN); if(dot(n, v) < 0.) n = -n;
  vec3 alb = texture(tex, vT).rgb;
  vec3 c = alb*(ambient + sunCol*max(dot(n,sunDir),0.));
  for(int i=0;i<6;i++){ if(i>=Ln) break;
    vec3 l = Lpos[i]-vP; float d2 = dot(l,l); float rr = d2/(Lrange[i]*Lrange[i]);
    float att = clamp(1.-rr*rr,0.,1.); att = att*att/(1.+25.*rr);
    c += alb*Lcol[i]*att*max(dot(n,normalize(l)),0.); }
  vec4 ov = overlay(vP, n, v); c = c*(1.-ov.a) + ov.rgb;
  c = mix(c, fogCol, 1.-exp(-length(camPos - vP)*fogD));
  o = vec4(c, 1.); }`;
const VS_PART = `#version 300 es""")

# E: depth buffer on the main HDR target
rep("""    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    return { t, fb, w, h };""", """    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, t, 0);
    if (depth) {
      const rb = gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER, rb);
      gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
      gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, rb);
    }
    return { t, fb, w, h };""")
rep("  target(w, h) {", "  target(w, h, depth) {")
rep("this.main = this.target(w, h);", "this.main = this.target(w, h, true);")

# programs + mesh cache
rep("this.pBright = this.prog(VS_FULL, FS_BRIGHT);", "this.pMesh = this.prog(VS_MESH, FS_MESH); this.meshes = {};\n    this.pBright = this.prog(VS_FULL, FS_BRIGHT);")
rep("  full(p) {", """  mesh(name) {
    if (this.meshes[name]) return this.meshes[name];
    const gl = this.gl, M = CREATURE_MESH[name], p = this.pMesh, vao = gl.createVertexArray();
    gl.bindVertexArray(vao);
    for (const [attr, arr, n] of [["aP", M.pos, 3], ["aN", M.nor, 3], ["aT", M.uv, 2]]) {
      const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, arr, gl.STATIC_DRAW);
      gl.enableVertexAttribArray(p.a[attr]); gl.vertexAttribPointer(p.a[attr], n, gl.FLOAT, false, 0, 0);
    }
    const ib = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, M.idx, gl.STATIC_DRAW);
    gl.bindVertexArray(null);
    this.loadTex("mesh:" + name, M.tex);
    return (this.meshes[name] = { vao, count: M.idx.length });
  }
  full(p) {""")

# F: render order: sky/ground, then mesh with depth, then particles depth-tested
rep("""    // particles
    const pp = this.pPart; gl.useProgram(pp); this.camUniforms(pp, cam, scene.cap);""", """    // creature mesh
    gl.clear(gl.DEPTH_BUFFER_BIT); gl.enable(gl.DEPTH_TEST); gl.depthMask(true);
    const pm = this.pMesh, me = this.mesh(scene.mesh); gl.useProgram(pm); this.camUniforms(pm, cam, scene.cap);
    gl.uniform1f(pm.u.projA, cam.projA); gl.uniform1f(pm.u.projB, cam.projB);
    gl.uniform3fv(pm.u.ambient, L.ambient); gl.uniform3fv(pm.u.sunDir, L.sunDir); gl.uniform3fv(pm.u.sunCol, L.sunCol); gl.uniform3fv(pm.u.fogCol, L.fogCol); gl.uniform1f(pm.u.fogD, L.fogD);
    gl.uniform3fv(pm.u.Lpos, lp); gl.uniform3fv(pm.u.Lcol, lc); gl.uniform1fv(pm.u.Lrange, lr); gl.uniform1i(pm.u.Ln, Math.min(lights.length, 6));
    gl.uniform4fv(pm.u.elemA, ov.slice(0, 4)); gl.uniform1f(pm.u.elemB, ov[4]); gl.uniform1f(pm.u.uTime, time);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, this.tex["mesh:" + scene.mesh] || this.white); gl.uniform1i(pm.u.tex, 0);
    gl.bindVertexArray(me.vao); gl.drawElements(gl.TRIANGLES, me.count, gl.UNSIGNED_SHORT, 0); gl.bindVertexArray(null);
    // particles
    gl.depthMask(false);
    const pp = this.pPart; gl.useProgram(pp); this.camUniforms(pp, cam, scene.cap);
    gl.uniform1f(pp.u.projA, cam.projA); gl.uniform1f(pp.u.projB, cam.projB);""")
rep("""    gl.disable(gl.BLEND);
    // bloom + tonemap""", """    gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST); gl.depthMask(true);
    // bloom + tonemap""")
rep("""    gl.uniform4fv(ps.u.elemA, ov.slice(0, 4)); gl.uniform1f(ps.u.elemB, ov[4]); gl.uniform1f(ps.u.uTime, time);
""", "")

# camera projection constants
rep("cam: (aspect) => ({ pos: camPos, f, r, u, tanH: Math.tan((65 / 2) * Math.PI / 180), aspect })",
    "mesh: state.target, cam: (aspect) => ({ pos: camPos, f, r, u, tanH: Math.tan((65 / 2) * Math.PI / 180), aspect, projA: (200 + 0.05) / (200 - 0.05), projB: (-2 * 200 * 0.05) / (200 - 0.05) })")

# H: emit from the actual mesh triangles, area weighted
a = s.index("    if (this.surf) {"); b = s.index("    }", s.index("wp = [d[0] * c.r")) + len("    }")
s = s[:a] + """    if (this.surf) {
      // overhaul: emit from the creature's own triangles, area weighted, like the mod's SkinnedMeshRenderer shape
      const M = this.surf, k = M.pickTri(R()), i0 = M.idx[k * 3] * 3, i1 = M.idx[k * 3 + 1] * 3, i2 = M.idx[k * 3 + 2] * 3;
      let u = R(), w = R(); if (u + w > 1) { u = 1 - u; w = 1 - w; }
      wp = [0, 1, 2].map((j) => M.pos[i0 + j] * (1 - u - w) + M.pos[i1 + j] * u + M.pos[i2 + j] * w);
      d = norm([0, 1, 2].map((j) => M.nor[i0 + j] * (1 - u - w) + M.nor[i1 + j] * u + M.nor[i2 + j] * w));
    }""" + s[b:]
rep('mod && state.mode === "overhaul" ? scene.cap : null', 'mod && state.mode === "overhaul" ? CREATURE_MESH[state.target] : null')

# L: decode embedded meshes
rep("const LINEAR_TEX = { flameball_big_flipbook: true };", """const LINEAR_TEX = { flameball_big_flipbook: true };
const MESHES = __MESHES__;
// Bind-pose creature meshes exported from the game bundle, already placed in the creature's root space (feet at y = 0).
const CREATURE_MESH = {};
for (const [name, m] of Object.entries(MESHES)) {
  const dec = (b64, T) => { const bin = atob(b64), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); return new T(u8.buffer); };
  const pos = dec(m.pos, Float32Array), idx = dec(m.idx, Uint16Array);
  const cdf = new Float32Array(idx.length / 3); let acc = 0;
  for (let t = 0; t < cdf.length; t++) {
    const a = idx[t * 3] * 3, b = idx[t * 3 + 1] * 3, c = idx[t * 3 + 2] * 3;
    const e1 = [pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]], e2 = [pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]];
    acc += Math.hypot(e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]) / 2; cdf[t] = acc;
  }
  const pickTri = (r) => { const x = r * acc; let lo = 0, hi = cdf.length - 1; while (lo < hi) { const mid = (lo + hi) >> 1; if (cdf[mid] < x) lo = mid + 1; else hi = mid; } return lo; };
  CREATURE_MESH[name] = { pos, nor: dec(m.nor, Float32Array), uv: dec(m.uv, Float32Array), idx, tex: m.tex, pickTri };
}""")
open(p, "w").write(s)
print("patched")
