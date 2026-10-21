using System.IO;
using UnityEditor;
using UnityEngine.Rendering;

public static class BuildBundle
{
    // Batch: Unity -batchmode -quit -projectPath . -executeMethod BuildBundle.Build
    // One bundle per player platform: shaders are compiled per graphics API, and Windows players
    // (including Linux via Proton) run DirectX 11 while native Linux Valheim runs Vulkan.
    [MenuItem("Valheim/Build elemental overlay bundles")]
    public static void Build()
    {
        Make(BuildTarget.StandaloneLinux64, "linux", GraphicsDeviceType.Vulkan, GraphicsDeviceType.OpenGLCore);
        Make(BuildTarget.StandaloneWindows64, "windows", GraphicsDeviceType.Direct3D11, GraphicsDeviceType.Vulkan);
    }

    static void Make(BuildTarget target, string name, params GraphicsDeviceType[] apis)
    {
        PlayerSettings.SetUseDefaultGraphicsAPIs(target, false);
        PlayerSettings.SetGraphicsAPIs(target, apis);
        var dir = Path.Combine("Build", name);
        Directory.CreateDirectory(dir);
        var bundle = new AssetBundleBuild { assetBundleName = "elementaloverlay_" + name, assetNames = new[] { "Assets/Shaders/ElementalOverlay.shader" } };
        if (!BuildPipeline.BuildAssetBundles(dir, new[] { bundle }, BuildAssetBundleOptions.ChunkBasedCompression, target))
            throw new System.Exception("Bundle build failed for " + name);
    }
}
