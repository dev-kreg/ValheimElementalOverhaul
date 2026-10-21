using System.IO;
using System.Linq;
using BepInEx.Configuration;
using HarmonyLib;
using UnityEngine;
using UnityEngine.Rendering;

namespace ElementalOverhaul
{
    // Overhaul driver: gives creatures with an elemental status an ElementalBody, and draws the elemental surface
    // shader over their skinned meshes. The shader comes from the elementaloverlay_<platform> bundles built by
    // the shader/ project; without it the particles and light still work, just no skin effect.
    public class Overlay : MonoBehaviour
    {
        // Slot order matches the shader's _ElemA (fire, frost, poison, lightning) and _ElemB (spirit).
        public static readonly int[] Hashes = { SEMan.s_statusEffectBurning, SEMan.s_statusEffectFrost, SEMan.s_statusEffectPoison, SEMan.s_statusEffectLightning, SEMan.s_statusEffectSpirit };
        static readonly int ElemA = Shader.PropertyToID("_ElemA"), ElemB = Shader.PropertyToID("_ElemB"), Age = Shader.PropertyToID("_ElemAge"),
            SunDir = Shader.PropertyToID("_ElemSunDir"), SceneLight = Shader.PropertyToID("_ElemLight"), Scale = Shader.PropertyToID("_ElemScale"),
            ShellH = Shader.PropertyToID("_ShellH"),
            Mask = Shader.PropertyToID("_ElemMask"), Cutoff = Shader.PropertyToID("_ElemCutoff");

        static ConfigEntry<bool> on;
        static ConfigEntry<float> range;
        static string dir;

        Material mat;
        CommandBuffer cb;
        Camera cam;

        public static int Slot(int nameHash) => System.Array.IndexOf(Hashes, nameHash);

        public static void Bind(ConfigFile config, string pluginDir)
        {
            dir = pluginDir;
            on = config.Bind("Overlay", "Enabled", true, "Draw the elemental surface shader on affected creatures (needs the elementaloverlay bundle)");
            range = config.Bind("Overlay", "MaxDistance", 50f, "Skip creatures farther than this from the camera, in metres");
        }

        void Start()
        {
            // shaders are compiled per graphics API: Windows (and Proton) uses the DirectX build, native Linux the Vulkan one
            var file = Application.platform == RuntimePlatform.WindowsPlayer ? "elementaloverlay_windows"
                : Application.platform == RuntimePlatform.LinuxPlayer ? "elementaloverlay_linux" : null;
            if (file == null) { Debug.LogWarning("[ElementalOverhaul] no overlay shader for " + Application.platform + "; particles and light only"); return; }
            var path = Path.Combine(dir, file);
            if (!File.Exists(path)) return;
            var bundle = AssetBundle.LoadFromFile(path);
            var shader = bundle ? bundle.LoadAllAssets<Shader>().FirstOrDefault() : null;
            if (!shader || !shader.isSupported)
            {
                Debug.LogWarning($"[ElementalOverhaul] overlay shader missing or unsupported in {path}");
                return;
            }
            mat = new Material(shader);
            cb = new CommandBuffer { name = "ElementalOverlay" };
            Debug.Log("[ElementalOverhaul] overlay shader loaded");
        }

        void LateUpdate()
        {
            if (!Plugin.Overhaul) return;
            var c = GameCamera.instance ? Traverse.Create(GameCamera.instance).Field<Camera>("m_camera").Value : Camera.main; // main menu has no GameCamera
            float maxSq = range.Value * range.Value;

            // give newly affected creatures nearby a body; bodies remove themselves once their effects fade
            if (c)
                foreach (var ch in Character.GetAllCharacters())
                    if (ch && (ch.transform.position - c.transform.position).sqrMagnitude <= maxSq && !ch.GetComponent<ElementalBody>()
                        && (Plugin.AnyForced || Hashes.Any(ch.GetSEMan().HaveStatusEffect)))
                        ch.gameObject.AddComponent<ElementalBody>();

            if (!mat) return;
            if (c != cam)
            {
                if (cam) cam.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, cb);
                cam = c;
                if (cam) cam.AddCommandBuffer(CameraEvent.AfterForwardAlpha, cb);
            }
            cb.Clear();
            if (!cam || !on.Value) return;
            P.Push(cb);
            cb.SetGlobalFloat(SceneLight, SceneLevel());
            var sun = RenderSettings.sun;
            cb.SetGlobalVector(SunDir, sun ? -sun.transform.forward : Vector3.up);
            int shells = Mathf.RoundToInt(P.GlobalShellCount.Value);

            foreach (var b in ElementalBody.All)
            {
                if (!b || (b.transform.position - cam.transform.position).sqrMagnitude > maxSq) continue;
                var lv = b.Level;
                cb.SetGlobalVector(ElemA, new Vector4(lv[0], lv[1], lv[2], lv[3]));
                cb.SetGlobalFloat(ElemB, lv[4]);
                var age = b.Age;
                cb.SetGlobalVector(Age, new Vector4(age[0], age[1], age[2], age[3]));
                cb.SetGlobalFloat(Scale, b.PatternScale);
                foreach (var r in b.Renderers)
                    if (r && r.isVisible && r.sharedMesh) // isVisible skips LOD levels that aren't drawn
                        for (int sub = 0; sub < r.sharedMesh.subMeshCount; sub++)
                        {
                            // match alpha-cutout parts (Lox fur cards) so the overlay doesn't draw their full quads
                            var m = sub < r.sharedMaterials.Length ? r.sharedMaterials[sub] : r.sharedMaterial;
                            bool cut = m && m.mainTexture && (m.IsKeywordEnabled("_ALPHATEST_ON") || (m.renderQueue >= 2450 && m.renderQueue < 3000));
                            cb.SetGlobalTexture(Mask, m && m.mainTexture ? m.mainTexture : Texture2D.grayTexture); // albedo for cast light, alpha for cutout
                            cb.SetGlobalFloat(Cutoff, cut ? (m.HasProperty("_Cutoff") ? m.GetFloat("_Cutoff") : 0.5f) : -1f);
                            cb.DrawRenderer(r, mat, sub, 0); // tint pass
                            cb.DrawRenderer(r, mat, sub, 1); // light pass
                            for (int k = 1; k <= shells; k++)
                            {
                                cb.SetGlobalFloat(ShellH, (float)k / shells);
                                cb.DrawRenderer(r, mat, sub, 2); // layer above the skin
                            }
                        }
            }
        }

        // 0 at night, ~1 in daylight: lets frost crust and sheen look lit rather than glowing
        static float SceneLevel()
        {
            var amb = RenderSettings.ambientMode == AmbientMode.Flat ? RenderSettings.ambientLight : RenderSettings.ambientSkyColor;
            float l = amb.grayscale * 1.5f;
            if (RenderSettings.sun) l += RenderSettings.sun.intensity * RenderSettings.sun.color.grayscale * 0.35f;
            return Mathf.Clamp01(l);
        }

        void OnDestroy()
        {
            if (cam && cb != null) cam.RemoveCommandBuffer(CameraEvent.AfterForwardAlpha, cb);
        }
    }
}
