using System.Collections.Generic;
using UnityEngine;
using PS = UnityEngine.ParticleSystem;

namespace ElementalOverhaul
{
    // Overhaul state for one creature with elemental status effects: per-element levels (also read by the overlay),
    // a few particles per element spawned from the body mesh, and one shared light. Removes itself when all levels fade out.
    // Particle settings mirror OVERHAUL in the browser preview; keep them in sync.
    public class ElementalBody : MonoBehaviour
    {
        public static readonly HashSet<ElementalBody> All = new HashSet<ElementalBody>();
        // Vanilla materials captured from the effect prefabs, keyed "prefab/child".
        public static readonly Dictionary<string, Material> Mats = new Dictionary<string, Material>();
        // Vanilla particle system objects from the effect prefabs, keyed "prefab/child", for cloning.
        public static readonly Dictionary<string, GameObject> Sources = new Dictionary<string, GameObject>();
        static readonly Dictionary<Mesh, float> areas = new Dictionary<Mesh, float>();

        // Slot order: fire, frost, poison, lightning, spirit (same as Overlay.Hashes and the shader).
        static readonly Color[] LightCol = { new Color(1f, 0.6f, 0.28f), new Color(0.6f, 0.8f, 1f), new Color(0.5f, 0.9f, 0.2f), new Color(0.4f, 0.78f, 1f), new Color(0.5f, 1f, 0.65f) };
        static readonly float[] LightInt = { 2f, 0.5f, 0.4f, 1.2f, 1.2f };

        struct Emitter { public PS ps; public BepInEx.Configuration.ConfigEntry<float> density; }

        public readonly float[] Level = new float[5];
        public readonly float[] Age = new float[5]; // seconds each element has been active (drives char build-up, frost spread)
        public SkinnedMeshRenderer[] Renderers;
        public float PatternScale => 1f / Mathf.Sqrt(Mathf.Max(height, 0.5f) / 1.8f); // 1 for a Greydwarf
        Character ch;
        SkinnedMeshRenderer body;
        float area, height, radius;
        readonly List<Emitter>[] emitters = new List<Emitter>[5];
        Light glow;

        void Awake()
        {
            ch = GetComponent<Character>();
            Renderers = GetComponentsInChildren<SkinnedMeshRenderer>();
            body = Plugin.Body(ch);
            radius = ch.GetRadius();
            var col = GetComponent<Collider>();
            height = col ? col.bounds.size.y : 2f;
            // ponytail: cap surface area so Troll/Lox don't flood; per-creature tuning if they still look sparse or busy
            area = Mathf.Min(body ? Area(body) : 2f * Mathf.PI * radius * height, 14f);

            var lg = new GameObject("QE_light");
            lg.transform.SetParent(transform, false);
            lg.transform.position = transform.position + Vector3.up * height * 0.6f;
            glow = lg.AddComponent<Light>();
            glow.type = LightType.Point;
            glow.shadows = LightShadows.None;
            glow.range = Mathf.Max(4f, height * 2.2f);
            All.Add(this);
        }

        void OnDestroy() => All.Remove(this); // particles and light are children, so they go with the creature

        // Effects ended while the creature lives: let live particles finish instead of popping, then remove ourselves.
        void Release()
        {
            if (glow) Destroy(glow.gameObject);
            foreach (var list in emitters)
                if (list != null)
                    foreach (var e in list)
                        if (e.ps)
                        {
                            e.ps.transform.SetParent(null, true);
                            e.ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
                            Destroy(e.ps.gameObject, 2.5f);
                        }
        }

        void Update()
        {
            var seman = ch.GetSEMan();
            float dt = Time.deltaTime;
            bool any = false;
            int active = 0;
            for (int i = 0; i < 5; i++)
            {
                // fast fade in on hit, slow fade out when the status ends
                bool on = seman.HaveStatusEffect(Overlay.Hashes[i]) || Plugin.Forced(i);
                Level[i] = Mathf.MoveTowards(Level[i], on ? 1f : 0f, dt * (on ? 6f : 1.5f));
                Age[i] = on ? Age[i] + dt : Level[i] > 0f ? Age[i] : 0f;
                any |= Level[i] > 0f;
                if (on) active++;
            }
            if (!any)
            {
                Release();
                Destroy(this);
                return;
            }

            float budget = 1f / Mathf.Sqrt(Mathf.Max(active, 1)); // stacked elements share the particle budget
            ComboPick(Level, out int combo, out float cw, out float allW);
            Color c = Color.black;
            float w = 0f, peak = 0f;
            for (int i = 0; i < 5; i++)
            {
                if (Level[i] > 0f && emitters[i] == null) emitters[i] = Build(i);
                if (emitters[i] != null)
                    foreach (var e in emitters[i])
                    {
                        var em = e.ps.emission;
                        em.rateOverTimeMultiplier = e.density.Value * P.GlobalParticleDensity.Value * area * budget * Level[i] * Keep(combo, cw, allW, i);
                    }
                c += LightCol[i] * LightInt[i] * Level[i];
                w += LightInt[i] * Level[i];
                if (Level[i] > 0f) peak = Mathf.Max(peak, LightInt[i] * Level[i]);
            }

            float t = Time.timeSinceLevelLoad; // matches the shader's _Time.y
            float flick = 0.82f + 0.18f * (Mathf.Sin(t * 9.1f + 1.7f) * 0.5f + Mathf.Sin(t * 23.7f + 3.4f) * 0.5f);
            if (Level[3] > 0f) flick *= Mathf.Lerp(1f, Mathf.Max(0f, 1f + P.LightningLightFlash.Value * (1.6f * Burst(t) - 0.4f)), Level[3]);
            glow.color = w > 0f ? c / w : Color.black;
            // a combo tints the light toward its own colour
            if (allW > 0f) glow.color = Color.Lerp(glow.color, P.CombosAllColor.Value, allW);
            else if (combo > 0) glow.color = Color.Lerp(glow.color, ComboColor(combo), cw);
            glow.intensity = peak * Plugin.LightMultiplier * 2f * flick;
        }

        // Mirrors comboPick/pairHas/keep in src/overlay.glsl. Slots: 0 fire, 1 frost, 2 poison, 3 lightning, 4 spirit.
        static readonly int[,] Pairs = { { 0, 1 }, { 0, 3 }, { 0, 2 }, { 0, 4 }, { 1, 3 }, { 1, 2 }, { 1, 4 }, { 3, 2 }, { 3, 4 }, { 2, 4 } };

        static bool ComboOn(int id)
        {
            switch (id)
            {
                case 1: return P.CombosSteamEnabled.Value;
                case 2: return P.CombosOverloadEnabled.Value;
                case 3: return P.CombosToxicBurnEnabled.Value;
                case 4: return P.CombosGhostFireEnabled.Value;
                case 5: return P.CombosConductiveIceEnabled.Value;
                case 6: return P.CombosFrozenVeinsEnabled.Value;
                case 7: return P.CombosWraithChillEnabled.Value;
                case 8: return P.CombosCorrosiveSparksEnabled.Value;
                case 9: return P.CombosSoulLightningEnabled.Value;
                default: return P.CombosBlightEnabled.Value;
            }
        }

        static Color ComboColor(int id)
        {
            switch (id)
            {
                case 1: return P.CombosSteamColor.Value;
                case 2: return P.CombosOverloadColor.Value;
                case 3: return P.CombosToxicBurnColor.Value;
                case 4: return P.CombosGhostFireColor.Value;
                case 5: return P.CombosConductiveIceColor.Value;
                case 6: return P.CombosFrozenVeinsColor.Value;
                case 7: return P.CombosWraithChillColor.Value;
                case 8: return P.CombosCorrosiveSparksColor.Value;
                case 9: return P.CombosSoulLightningColor.Value;
                default: return P.CombosBlightColor.Value;
            }
        }

        static void ComboPick(float[] lv, out int id, out float w, out float allW)
        {
            id = 0; w = 0f;
            float on = P.CombosEnabled.Value ? 1f : 0f;
            allW = Mathf.Min(Mathf.Min(Mathf.Min(lv[0], lv[1]), Mathf.Min(lv[2], lv[3])), lv[4]) * (P.CombosAllEnabled.Value ? on : 0f);
            if (allW > 0.001f) return; // Ragnarok takes over
            for (int k = 0; k < 10; k++)
            {
                float c = Mathf.Min(lv[Pairs[k, 0]], lv[Pairs[k, 1]]) * (ComboOn(k + 1) ? on : 0f);
                if (c > w + 0.001f) { w = c; id = k + 1; }
            }
        }

        static float Keep(int id, float w, float allW, int slot)
        {
            bool inPair = id > 0 && (Pairs[id - 1, 0] == slot || Pairs[id - 1, 1] == slot);
            return 1f - P.CombosReplace.Value * Mathf.Max(allW, inPair ? w : 0f);
        }

        // Same hash and timing as the shader's lightning gate, so the light flashes with the arcs.
        static float Frac(float x) => x - Mathf.Floor(x);
        static float H3(float x, float y, float z)
        {
            x = Frac(x * 0.3183099f + 0.1f) * 17f;
            y = Frac(y * 0.3183099f + 0.1f) * 17f;
            z = Frac(z * 0.3183099f + 0.1f) * 17f;
            return Frac(x * y * z * (x + y + z));
        }
        static float Burst(float t) => (H3(Mathf.Floor(t * P.LightningBurstRate.Value), 1.3f, 2.1f) >= 1f - P.LightningBurstChance.Value ? 1f : 0f)
            * (H3(Mathf.Floor(t * P.LightningFlickerRate.Value), 0.37f, 0.71f) >= 0.25f ? 1f : 0f);

        static float Area(SkinnedMeshRenderer r)
        {
            var m = r.sharedMesh;
            if (!areas.TryGetValue(m, out var a))
            {
                var v = m.vertices;
                var tri = m.triangles;
                var s = r.transform.lossyScale;
                for (int i = 0; i < tri.Length; i += 3)
                {
                    var p0 = Vector3.Scale(v[tri[i]], s);
                    a += Vector3.Cross(Vector3.Scale(v[tri[i + 1]], s) - p0, Vector3.Scale(v[tri[i + 2]], s) - p0).magnitude * 0.5f;
                }
                areas[m] = a;
            }
            return a;
        }

        List<Emitter> Build(int slot)
        {
            var list = new List<Emitter>();
            switch (slot)
            {
                case 0: // fire: flame tongues licking up the body (game flipbook) + rising embers
                    // the game's own flame system, cloned: its gradient-mapped material needs the custom data
                    // streams and flame gradient that only the vanilla system provides
                    list.Add(Clone("tongues", P.FireTongueDensity, "vfx_Burning/flames (1)", ps =>
                    {
                        Size(ps, P.FireTongueSize.Value);
                        Vel(ps, 0.08f, P.FireTongueRise.Value * 0.65f, P.FireTongueRise.Value * 1.3f);
                    }));
                    list.Add(Make("embers", P.FireEmberDensity, Mat("vfx_Burning/sparcs (1)"), ps =>
                    {
                        var m = ps.main;
                        m.startLifetime = new PS.MinMaxCurve(1f, 2f);
                        Size(ps, P.FireEmberSize.Value);
                        m.startColor = new PS.MinMaxGradient(new Color(1f, 0.77f, 0f), Color.white);
                        Vel(ps, 0f, 0.6f, 1.3f);
                        Noise(ps, 0.6f, 1.2f, 0.1f);
                        var col = ps.colorOverLifetime; col.enabled = true;
                        col.color = Grad(0f, 1f, 0.9f, 0.5f, 0f, 0.1f, 1f, 0.8f, 0.4f, 1f, 1f, 1f, 0.3f, 0.05f, 0f);
                        var sol = ps.sizeOverLifetime; sol.enabled = true;
                        sol.size = Curve(0f, 1f, 1f, 0f);
                    }));
                    break;
                case 1: // frost: falling ice flakes
                    list.Add(Make("flakes", P.FrostFlakeDensity, Tinted("vfx_Frost/vfx_BloodHit 1", new Color(1.2f, 1.2f, 1.2f, 1f)), ps =>
                    {
                        var m = ps.main;
                        m.startLifetime = new PS.MinMaxCurve(1.2f, 2.2f);
                        Size(ps, P.FrostFlakeSize.Value);
                        m.startColor = new PS.MinMaxGradient(new Color(0.85f, 0.93f, 1f, 0.9f), new Color(1f, 1f, 1f, 0.9f));
                        Vel(ps, 0.05f, -P.FrostFlakeFall.Value * 1.4f, -P.FrostFlakeFall.Value * 0.6f);
                        Noise(ps, 0.2f, 2f, 0.05f);
                        var col = ps.colorOverLifetime; col.enabled = true;
                        col.color = Grad(0f, 1f, 1f, 1f, 0f, 0.15f, 1f, 1f, 1f, 1f, 0.8f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 0f);
                    }));
                    break;
                case 2: // poison: drips
                    list.Add(Make("drips", P.PoisonDripDensity, Tinted("vfx_Frost/vfx_BloodHit 1", Color.white), ps =>
                    {
                        var m = ps.main;
                        m.startLifetime = new PS.MinMaxCurve(0.6f, 0.95f);
                        Size(ps, P.PoisonDripSize.Value);
                        m.startColor = new PS.MinMaxGradient(new Color(0.42f, 0.8f, 0.08f, 0.95f), new Color(0.55f, 0.9f, 0.15f, 0.95f));
                        m.gravityModifier = 0.55f;
                        var col = ps.colorOverLifetime; col.enabled = true;
                        col.color = Grad(0f, 1f, 1f, 1f, 0f, 0.1f, 1f, 1f, 1f, 1f, 0.85f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 0f);
                        var r = ps.GetComponent<ParticleSystemRenderer>();
                        r.renderMode = ParticleSystemRenderMode.Stretch;
                        r.lengthScale = 2.4f;
                    }));
                    break;
                case 3: // lightning: brief zigzag sparks on the surface
                    list.Add(Make("sparks", P.LightningSparkDensity, Mat("fx_Lightning/Sparcs"), ps =>
                    {
                        var m = ps.main;
                        m.startLifetime = new PS.MinMaxCurve(0.06f, 0.12f);
                        Size(ps, P.LightningSparkSize.Value);
                        m.startRotation = new PS.MinMaxCurve(0f, 6.28f);
                    }));
                    break;
                case 4: // spirit: rising wisps drawn as trails only
                    list.Add(Make("wisps", P.SpiritWispDensity, Mat("vfx_UndeadBurn/trails"), ps =>
                    {
                        var m = ps.main;
                        m.startLifetime = new PS.MinMaxCurve(1f, 2f);
                        Size(ps, 0.02f);
                        m.startColor = new PS.MinMaxGradient(new Color(0.01f, 0.78f, 0.65f), new Color(0.17f, 0.88f, 0.79f));
                        Vel(ps, 0f, P.SpiritWispRise.Value * 0.6f, P.SpiritWispRise.Value * 1.4f);
                        Noise(ps, 0.5f, 1f, 0.1f);
                        var col = ps.colorOverLifetime; col.enabled = true;
                        col.color = Grad(0f, 1f, 0.9f, 0.5f, 0f, 0.1f, 1f, 0.85f, 0.47f, 1f, 1f, 0.9f, 0.3f, 0.3f, 0f);
                        var tr = ps.trails; tr.enabled = true;
                        tr.lifetime = 0.35f;
                        tr.widthOverTrail = Curve(0f, 1f, 1f, 0f);
                        tr.colorOverTrail = Grad(0f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 1f, 0f);
                        var r = ps.GetComponent<ParticleSystemRenderer>();
                        r.renderMode = ParticleSystemRenderMode.None;
                        r.trailMaterial = Mat("vfx_UndeadBurn/trails#trail");
                    }));
                    break;
            }
            list.RemoveAll(e => !e.ps);
            return list;
        }

        // Copy a vanilla particle system (keeps material, custom data, vertex streams, colour and UV animation),
        // then retarget it: emit from the body, rate driven by us, world space.
        Emitter Clone(string name, BepInEx.Configuration.ConfigEntry<float> density, string key, System.Action<PS> setup)
        {
            if (!Sources.TryGetValue(key, out var src) || !src) return default;
            var go = Instantiate(src, transform, false);
            go.name = "QE_" + name;
            go.SetActive(true);
            go.transform.localPosition = Vector3.zero;
            go.transform.localRotation = Quaternion.identity;
            go.transform.localScale = Vector3.one;
            foreach (Transform child in go.transform) Destroy(child.gameObject);
            var ps = go.GetComponent<PS>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Shape;
            main.maxParticles = 200;
            var em = ps.emission;
            em.rateOverTime = 0f;
            em.SetBursts(new PS.Burst[0]);
            var lights = ps.lights; lights.enabled = false;
            var subs = ps.subEmitters; subs.enabled = false;
            Shape(ps);
            setup(ps);
            ps.Play();
            return new Emitter { ps = ps, density = density };
        }

        void Shape(PS ps)
        {
            var sh = ps.shape;
            sh.enabled = true;
            sh.position = Vector3.zero;
            sh.rotation = Vector3.zero;
            sh.scale = Vector3.one;
            if (body)
            {
                sh.shapeType = ParticleSystemShapeType.SkinnedMeshRenderer;
                sh.skinnedMeshRenderer = body;
                sh.meshShapeType = ParticleSystemMeshShapeType.Triangle;
            }
            else
            {
                sh.shapeType = ParticleSystemShapeType.Sphere;
                sh.radius = radius;
                ps.transform.position = transform.position + Vector3.up * height * 0.5f;
            }
        }

        Emitter Make(string name, BepInEx.Configuration.ConfigEntry<float> density, Material mat, System.Action<PS> setup)
        {
            if (!mat) return default; // ponytail: missing vanilla material (game update) just skips this emitter
            var go = new GameObject("QE_" + name);
            go.transform.SetParent(transform, false);
            var ps = go.AddComponent<PS>();
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
            var main = ps.main;
            main.loop = true;
            main.playOnAwake = false;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.scalingMode = ParticleSystemScalingMode.Shape;
            main.startSpeed = 0f;
            main.maxParticles = 200;
            var em = ps.emission;
            em.rateOverTime = 0f;
            var sh = ps.shape;
            sh.enabled = true;
            if (body)
            {
                sh.shapeType = ParticleSystemShapeType.SkinnedMeshRenderer;
                sh.skinnedMeshRenderer = body;
                sh.meshShapeType = ParticleSystemMeshShapeType.Triangle;
            }
            else
            {
                sh.shapeType = ParticleSystemShapeType.Sphere;
                sh.radius = radius;
                go.transform.position = transform.position + Vector3.up * height * 0.5f;
            }
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = mat;
            r.renderMode = ParticleSystemRenderMode.Billboard;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            setup(ps);
            ps.Play();
            return new Emitter { ps = ps, density = density };
        }

        static Material Mat(string key) => Mats.TryGetValue(key, out var m) ? m : null;

        static Material Tinted(string key, Color c)
        {
            var src = Mat(key);
            if (!src) return null;
            var tk = key + "#" + c;
            if (!Mats.TryGetValue(tk, out var m))
            {
                m = new Material(src);
                m.SetColor("_Color", c);
                Mats[tk] = m;
            }
            return m;
        }

        // size given as the middle of a +-30% random range, scaled by the global particle size
        static void Size(PS ps, float size)
        {
            var m = ps.main;
            float s = size * P.GlobalParticleSize.Value;
            m.startSize = new PS.MinMaxCurve(s * 0.7f, s * 1.3f);
        }

        static void Vel(PS ps, float xz, float yMin, float yMax)
        {
            var v = ps.velocityOverLifetime;
            v.enabled = true;
            v.space = ParticleSystemSimulationSpace.World;
            v.x = new PS.MinMaxCurve(-xz, xz);
            v.y = new PS.MinMaxCurve(yMin, yMax);
            v.z = new PS.MinMaxCurve(-xz, xz);
        }

        static void Noise(PS ps, float strength, float frequency, float scroll)
        {
            var n = ps.noise;
            n.enabled = true;
            n.strength = strength;
            n.frequency = frequency;
            n.scrollSpeed = scroll;
        }

        // keys as (time, r, g, b, a) quintuples
        static PS.MinMaxGradient Grad(params float[] k)
        {
            int n = k.Length / 5;
            var c = new GradientColorKey[n];
            var a = new GradientAlphaKey[n];
            for (int i = 0; i < n; i++)
            {
                c[i] = new GradientColorKey(new Color(k[i * 5 + 1], k[i * 5 + 2], k[i * 5 + 3]), k[i * 5]);
                a[i] = new GradientAlphaKey(k[i * 5 + 4], k[i * 5]);
            }
            var g = new Gradient();
            g.SetKeys(c, a);
            return new PS.MinMaxGradient(g);
        }

        // keys as (time, value) pairs
        static PS.MinMaxCurve Curve(params float[] k)
        {
            var ac = new AnimationCurve();
            for (int i = 0; i < k.Length; i += 2) ac.AddKey(k[i], k[i + 1]);
            return new PS.MinMaxCurve(1f, ac);
        }
    }
}
