using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BepInEx;
using HarmonyLib;
using UnityEngine;

namespace QETestbed
{
    // Test harness for the QuietElements VFX. Does nothing unless Valheim is launched with -qetest.
    // With it: skips the intro and menus, boots a throwaway local character + world ("qetest"), makes the player
    // invincible and ignored, and runs commands written to BepInEx/plugins/QETestbed/testbed.cmd (one per line):
    //   spawn <Prefab> [count]        replace the dummies with a row of AI-less, unkillable creatures
    //   apply <fire,frost,...|none>   respawn the dummies fresh, then keep these elements on them (real status effects)
    //   cam <dist> <yaw> <height>     orbit camera around the dummies (metres, degrees, metres)
    //   time <0..1>                   time of day (0.5 = noon)
    //   env <name>                    force an environment, e.g. Clear, Misty, ThunderStorm ("" to release)
    //   hud <on|off>                  show or hide the HUD
    //   record <name> <frames> <fps>  save a square centre crop as shots/<name>/NNN.jpg (for GIFs)
    //   shot <name>                   screenshot to BepInEx/plugins/QETestbed/shots/<name>.png
    //   quit                          exit the game
    // Every executed command is echoed to testbed.log.
    [BepInPlugin("claude.qetestbed", "QETestbed", "0.1.0")]
    public class Testbed : BaseUnityPlugin
    {
        const string Name = "qetest";
        static bool active;
        static Testbed inst;

        string dir, cmdPath, logPath;
        readonly List<Character> dummies = new List<Character>();
        readonly HashSet<string> elements = new HashSet<string>();
        bool ready, camOn = true;
        float nextHit, nextPoll;
        float camDist = 4f, camYaw = 0f, camHeight = 1.2f;
        Vector3 origin, forward;
        string lastPrefab = "Greydwarf";
        int lastCount = 1;

        void Awake()
        {
            active = Environment.GetCommandLineArgs().Contains("-qetest");
            if (!active) return;
            inst = this;
            dir = Path.GetDirectoryName(Info.Location);
            cmdPath = Path.Combine(dir, "testbed.cmd");
            logPath = Path.Combine(dir, "testbed.log");
            File.WriteAllText(cmdPath, "");
            File.WriteAllText(logPath, "testbed active\n");
            Application.runInBackground = true;
            Harmony.CreateAndPatchAll(typeof(Testbed));
        }

        void Log(string s)
        {
            File.AppendAllText(logPath, $"{DateTime.Now:HH:mm:ss} {s}\n");
            Logger.LogInfo(s);
        }

        static IEnumerator Nothing() { yield break; }

        [HarmonyPrefix, HarmonyPatch(typeof(FejdStartup), "TryPlayIntroCinematic")]
        static bool SkipIntro(ref IEnumerator __result)
        {
            __result = Nothing();
            return false;
        }

        [HarmonyPostfix, HarmonyPatch(typeof(FejdStartup), "Start")]
        static void AutoStart(FejdStartup __instance) => inst.StartCoroutine(inst.StartWorld(__instance));

        IEnumerator StartWorld(FejdStartup menu)
        {
            yield return new WaitForSeconds(2f); // let the menu finish its own setup (backend, profiles)
            var t = Traverse.Create(menu);
            if (!PlayerProfile.HaveProfile(Name))
            {
                var profile = new PlayerProfile(Name, FileHelpers.FileSource.Local);
                profile.SetName("QE Tester"); // fresh character: no player data copied from the menu preview
                profile.m_firstSpawn = false;  // no valkyrie intro
                profile.Save();
                Log("created test character");
            }
            Game.SetProfile(Name, FileHelpers.FileSource.Local);
            var world = World.GetCreateWorld(Name, FileHelpers.FileSource.Local);
            ZNet.m_onlineBackend = OnlineBackendType.Steamworks;
            ZNet.SetServer(true, false, false, Name, "", world);
            ZNet.ResetServerHost();
            t.Field("m_startingWorld").SetValue(true);
            t.Method("TransitionToMainScene").GetValue();
            Log("starting test world");
        }

        void Update()
        {
            if (!active) return;
            var p = Player.m_localPlayer;
            if (!ready && p && ZNetScene.instance && !p.IsTeleporting())
            {
                ready = true;
                p.SetGodMode(true);
                p.SetGhostMode(true);
                if (EnvMan.instance) { EnvMan.instance.m_debugTimeOfDay = true; EnvMan.instance.m_debugTime = 0.5f; }
                forward = Vector3.ProjectOnPlane(p.transform.forward, Vector3.up).normalized;
                origin = p.transform.position + forward * 5f;
                Spawn("Greydwarf", 1);
                if (Hud.instance) Hud.instance.m_userHidden = true;
                Log("ready");
            }
            if (ready && elements.Count > 0 && Time.time > nextHit)
            {
                nextHit = Time.time + 2f;
                foreach (var d in dummies) if (d) Apply(d);
            }
            if (Time.time > nextPoll)
            {
                nextPoll = Time.time + 0.5f;
                Poll();
            }
        }

        void Poll()
        {
            string[] lines;
            try
            {
                if (new FileInfo(cmdPath).Length == 0) return;
                lines = File.ReadAllLines(cmdPath);
                File.WriteAllText(cmdPath, "");
            }
            catch (IOException) { return; }
            foreach (var raw in lines)
            {
                var line = raw.Trim();
                if (line.Length == 0) continue;
                try { Run(line.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries)); Log("ok: " + line); }
                catch (Exception e) { Log($"failed: {line}: {e.Message}"); }
            }
        }

        void Run(string[] a)
        {
            switch (a[0])
            {
                case "spawn": Spawn(a[1], a.Length > 2 ? int.Parse(a[2]) : 1); break;
                case "apply":
                    Spawn(lastPrefab, lastCount); // fresh dummies: earlier status effects would otherwise linger
                    elements.Clear();
                    if (a.Length > 1 && a[1] != "none")
                        foreach (var e in a[1].Split(',')) elements.Add(e.Trim().ToLowerInvariant());
                    nextHit = 0f;
                    break;
                case "cam":
                    camDist = float.Parse(a[1], System.Globalization.CultureInfo.InvariantCulture);
                    if (a.Length > 2) camYaw = float.Parse(a[2], System.Globalization.CultureInfo.InvariantCulture);
                    if (a.Length > 3) camHeight = float.Parse(a[3], System.Globalization.CultureInfo.InvariantCulture);
                    camOn = true;
                    break;
                case "time": EnvMan.instance.m_debugTimeOfDay = true; EnvMan.instance.m_debugTime = float.Parse(a[1], System.Globalization.CultureInfo.InvariantCulture); break;
                case "env": EnvMan.instance.SetForceEnvironment(a.Length > 1 ? a[1] : ""); break;
                case "shot":
                    Directory.CreateDirectory(Path.Combine(dir, "shots"));
                    ScreenCapture.CaptureScreenshot(Path.Combine(dir, "shots", (a.Length > 1 ? a[1] : DateTime.Now.ToString("HHmmss")) + ".png"));
                    break;
                case "record": // record <name> <frames> <fps>: centre crop, 720x720 JPGs in shots/<name>/
                    StartCoroutine(Record(a[1], int.Parse(a[2]), float.Parse(a[3], System.Globalization.CultureInfo.InvariantCulture)));
                    break;
                case "hud": Hud.instance.m_userHidden = a.Length > 1 && a[1] == "off"; break;
                case "quit": Application.Quit(); break;
                default: throw new ArgumentException("unknown command");
            }
        }

        IEnumerator Record(string name, int frames, float fps)
        {
            var outDir = Path.Combine(dir, "shots", name);
            Directory.CreateDirectory(outDir);
            // linear RT: copy the captured pixels as-is (an sRGB target would gamma-encode them a second time)
            var rt = new RenderTexture(720, 720, 0, RenderTextureFormat.ARGB32, RenderTextureReadWrite.Linear);
            var tex = new Texture2D(720, 720, TextureFormat.RGB24, false);
            for (int i = 0; i < frames; i++)
            {
                yield return new WaitForEndOfFrame();
                var full = ScreenCapture.CaptureScreenshotAsTexture();
                float side = Mathf.Min(full.width, full.height) * 0.8f; // square centre crop around the dummies
                var scale = new Vector2(side / full.width, side / full.height);
                Graphics.Blit(full, rt, scale, new Vector2((1f - scale.x) / 2f, (1f - scale.y) / 2f - 0.02f));
                Destroy(full);
                var prev = RenderTexture.active;
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, 720, 720), 0, 0);
                RenderTexture.active = prev;
                File.WriteAllBytes(Path.Combine(outDir, $"{i:000}.jpg"), tex.EncodeToJPG(88));
                yield return new WaitForSeconds(1f / fps);
            }
            Destroy(rt);
            Destroy(tex);
            Log("recorded " + name);
        }

        void Spawn(string prefabName, int count)
        {
            lastPrefab = prefabName;
            lastCount = count;
            foreach (var d in dummies) if (d) ZNetScene.instance.Destroy(d.gameObject);
            dummies.Clear();
            var prefab = ZNetScene.instance.GetPrefab(prefabName) ?? throw new ArgumentException("no prefab " + prefabName);
            var right = Vector3.Cross(Vector3.up, forward);
            for (int i = 0; i < count; i++)
            {
                var pos = origin + right * ((i - (count - 1) / 2f) * 3f);
                if (ZoneSystem.instance.GetSolidHeight(pos, out float h)) pos.y = h;
                var go = Instantiate(prefab, pos, Quaternion.LookRotation(-forward));
                foreach (var ai in go.GetComponents<BaseAI>()) ai.enabled = false; // stands still, never attacks
                var ch = go.GetComponent<Character>();
                ch.SetMaxHealth(1e6f);
                ch.SetHealth(1e6f);
                dummies.Add(ch);
            }
        }

        // Real status effects through the game's own code path, without a hit (no blood, no stagger).
        void Apply(Character ch)
        {
            ch.SetHealth(1e6f);
            var t = Traverse.Create(ch);
            void Add(string elem, string method)
            {
                // frost's freeze time scales with damage / max health, so hit it with the full (huge) max health
                float dmg = elem == "frost" ? ch.GetMaxHealth() : 25f;
                if (elements.Contains(elem)) t.Method(method, new[] { typeof(float), typeof(short) }).GetValue(dmg, (short)0);
            }
            Add("fire", "AddFireDamage");
            Add("frost", "AddFrostDamage");
            Add("poison", "AddPoisonDamage");
            Add("lightning", "AddLightningDamage");
            Add("spirit", "AddSpiritDamage");
        }

        // Orbit camera around the dummies (runs after the game's own camera update).
        [HarmonyPostfix, HarmonyPatch(typeof(GameCamera), "LateUpdate")]
        static void Camera(GameCamera __instance)
        {
            if (!active || !inst.ready || !inst.camOn || inst.dummies.Count == 0) return;
            var center = inst.dummies.Where(d => d).Select(d => d.GetCenterPoint()).Aggregate(Vector3.zero, (s, v) => s + v) / Math.Max(1, inst.dummies.Count(d => d));
            var dir = Quaternion.Euler(0f, inst.camYaw, 0f) * -inst.forward;
            __instance.transform.position = center + dir * inst.camDist + Vector3.up * (inst.camHeight - 0.6f);
            __instance.transform.rotation = Quaternion.LookRotation(center - __instance.transform.position);
        }
    }
}
