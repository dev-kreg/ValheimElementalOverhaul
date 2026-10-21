using System.Collections.Generic;
using System.Linq;
using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;
using UnityEngine;

namespace ElementalOverhaul
{
    // Client-side only. Two modes for the elemental status effects (fire/frost/poison/lightning/spirit) that stack
    // on a target hit by a multi-element weapon:
    //   Overhaul: hide the vanilla particles and lights, draw the effect on the creature's skin, add a few surface particles.
    //   Quiet: keep the vanilla effects but shrink them (prefabs edited once, so changes need a restart).
    [BepInPlugin("ElementalOverhaul", "ElementalOverhaul", "0.9.1")]
    public class Plugin : BaseUnityPlugin
    {
        public enum Style { Overhaul, Quiet }

        static ConfigEntry<Style> mode;
        static ConfigEntry<float> size, emission, light;
        static ConfigEntry<string> effects;
        static ConfigEntry<bool> surface, debugShot;
        static ConfigEntry<string> debugElements;
        static readonly bool[] forced = new bool[5];
        static readonly HashSet<GameObject> done = new HashSet<GameObject>();

        static volatile bool reload;

        public static bool Overhaul => mode.Value == Style.Overhaul;
        public static bool Forced(int slot) => forced[slot];
        public static bool AnyForced => forced.Any(f => f);

        static void ParseForced()
        {
            var names = debugElements.Value.ToLowerInvariant().Split(',').Select(x => x.Trim()).ToList();
            string[] slots = { "fire", "frost", "poison", "lightning", "spirit" };
            for (int i = 0; i < 5; i++) forced[i] = names.Contains(slots[i]);
        }

        void Update()
        {
            if (debugShot.Value)
            {
                debugShot.Value = false;
                var dir = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(Info.Location), "shots");
                System.IO.Directory.CreateDirectory(dir);
                var file = System.IO.Path.Combine(dir, $"qe_{System.DateTime.Now:HHmmss}.png");
                ScreenCapture.CaptureScreenshot(file);
                Logger.LogInfo("screenshot " + file);
            }
            if (!reload) return;
            reload = false;
            bool save = Config.SaveOnConfigSet;
            Config.SaveOnConfigSet = false; // reloading must not write the file back, or the watcher fires again
            Config.Reload();
            Config.SaveOnConfigSet = save;
            Logger.LogInfo("config reloaded");
        }
        public static float LightMultiplier => light.Value;

        void Awake()
        {
            mode = Config.Bind("General", "Mode", Style.Overhaul, "Overhaul: effects on the creature's body. Quiet: smaller vanilla effects. Needs a restart.");
            size = Config.Bind("General", "SizeMultiplier", 0.5f, "Quiet mode: particle size (1 = vanilla)");
            emission = Config.Bind("General", "EmissionMultiplier", 0.4f, "Quiet mode: particle count (1 = vanilla)");
            light = Config.Bind("General", "LightMultiplier", 0.3f, "Glow light intensity (1 = vanilla)");
            effects = Config.Bind("General", "StatusEffects", "Burning,Frost,Poison,Lightning,Spirit", "Quiet mode: status effect names to shrink");
            surface = Config.Bind("Surface", "EmitFromBody", true, "Quiet mode: spawn the vanilla particles on the creature's mesh instead of a sphere around its center");
            P.Bind(Config);
            debugElements = Config.Bind("Debug", "PreviewElements", "", "Testing: comma list of fire, frost, poison, lightning, spirit forced onto every nearby creature and the menu character (empty = off)");
            debugShot = Config.Bind("Debug", "Screenshot", false, "Testing: set to true to save a screenshot to BepInEx/plugins/ElementalOverhaul/shots (switches itself back off)");
            debugElements.SettingChanged += (_, __) => ParseForced();
            ParseForced();
            Overlay.Bind(Config, System.IO.Path.GetDirectoryName(Info.Location));
            // live tuning: edits to the .cfg apply in game without a restart
            var watcher = new System.IO.FileSystemWatcher(System.IO.Path.GetDirectoryName(Config.ConfigFilePath), System.IO.Path.GetFileName(Config.ConfigFilePath));
            watcher.Changed += (_, __) => reload = true;
            watcher.Created += (_, __) => reload = true; // editors and sed -i replace the file instead of writing in place
            watcher.Renamed += (_, __) => reload = true;
            watcher.EnableRaisingEvents = true;
            gameObject.AddComponent<Overlay>();
            Harmony.CreateAndPatchAll(typeof(Plugin));
        }

        // ponytail: also affects the player's own burning/frost VFX, since vanilla shares one prefab per element.
        [HarmonyPostfix, HarmonyPatch(typeof(ObjectDB), "Awake")]
        static void OnObjectDB(ObjectDB __instance) // not "Prepare": Harmony reserves that name for its own setup hook
        {
            var names = effects.Value.Split(',').Select(s => s.Trim()).ToList();
            foreach (var se in __instance.m_StatusEffects.Where(s => s && Overlay.Slot(s.NameHash()) >= 0))
                foreach (var field in AccessTools.GetDeclaredFields(se.GetType()).Concat(AccessTools.GetDeclaredFields(typeof(StatusEffect))).Distinct())
                    if (field.FieldType == typeof(EffectList) && field.GetValue(se) is EffectList list)
                        foreach (var e in list.m_effectPrefabs)
                            if (e.m_prefab && done.Add(e.m_prefab))
                            {
                                Capture(e.m_prefab);
                                if (!Overhaul && names.Contains(se.name)) Shrink(e.m_prefab);
                                // start effects are hidden per instance in OnStart; the rest (poison's per-second tick cloud) on the prefab
                                if (Overhaul && field.Name != "m_startEffects") Hide(e.m_prefab);
                            }
        }

        // Keep the vanilla materials so the overhaul particles share the game's own look.
        static void Capture(GameObject prefab)
        {
            foreach (var r in prefab.GetComponentsInChildren<ParticleSystemRenderer>(true))
            {
                var key = prefab.name + "/" + r.gameObject.name;
                if (r.sharedMaterial) ElementalBody.Mats[key] = r.sharedMaterial;
                ElementalBody.Sources[key] = r.gameObject;
                if (r.trailMaterial) ElementalBody.Mats[key + "#trail"] = r.trailMaterial;
            }
        }

        [HarmonyPostfix, HarmonyPatch(typeof(StatusEffect), "TriggerStartEffects")]
        static void OnStart(StatusEffect __instance, Character ___m_character, GameObject[] ___m_startEffectInstances)
        {
            if (___m_startEffectInstances == null || !___m_character || Overlay.Slot(__instance.NameHash()) < 0) return;
            if (Overhaul)
            {
                foreach (var go in ___m_startEffectInstances)
                    if (go) Hide(go);
                return;
            }
            if (!surface.Value) return;
            var body = Body(___m_character);
            if (!body) return; // ponytail: non-readable meshes (Draugr, Seeker) keep the vanilla sphere
            foreach (var go in ___m_startEffectInstances)
                if (go)
                    foreach (var ps in go.GetComponentsInChildren<ParticleSystem>(true))
                    {
                        var sh = ps.shape;
                        if (!sh.enabled || ps.main.maxParticles == 0) continue;
                        sh.shapeType = ParticleSystemShapeType.SkinnedMeshRenderer;
                        sh.skinnedMeshRenderer = body;
                        sh.meshShapeType = ParticleSystemMeshShapeType.Triangle;
                        sh.position = Vector3.zero;
                        sh.rotation = Vector3.zero;
                        sh.scale = Vector3.one;
                    }
        }

        // hide vanilla visuals but keep their sounds
        static void Hide(GameObject go)
        {
            foreach (var r in go.GetComponentsInChildren<ParticleSystemRenderer>(true)) r.enabled = false;
            foreach (var l in go.GetComponentsInChildren<Light>(true)) l.enabled = false;
        }

        public static SkinnedMeshRenderer Body(Character c) => c.GetComponentsInChildren<SkinnedMeshRenderer>()
            .Where(r => r.enabled && r.sharedMesh && r.sharedMesh.isReadable)
            .OrderByDescending(r => r.sharedMesh.vertexCount)
            .FirstOrDefault();

        static void Shrink(GameObject prefab)
        {
            foreach (var ps in prefab.GetComponentsInChildren<ParticleSystem>(true))
            {
                var main = ps.main;
                main.startSize = Scale(main.startSize, size.Value);
                main.maxParticles = Mathf.CeilToInt(main.maxParticles * emission.Value); // keeps 0 at 0: each root system is a disabled-by-maxParticles blood burst
                var em = ps.emission;
                em.rateOverTime = Scale(em.rateOverTime, emission.Value);
                em.rateOverDistance = Scale(em.rateOverDistance, emission.Value);
                for (int i = 0; i < em.burstCount; i++)
                {
                    var b = em.GetBurst(i);
                    b.count = Scale(b.count, emission.Value);
                    em.SetBurst(i, b);
                }
            }
            // LightFlicker caches intensity in Awake, so editing the prefab carries through.
            foreach (var l in prefab.GetComponentsInChildren<Light>(true))
                l.intensity *= light.Value;
        }

        static ParticleSystem.MinMaxCurve Scale(ParticleSystem.MinMaxCurve c, float f)
        {
            c.constant *= f;
            c.constantMin *= f;
            c.constantMax *= f;
            c.curveMultiplier *= f;
            return c;
        }
    }
}
