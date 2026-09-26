using System.IO.Compression;
using Xunit;

namespace OniModern.Core.Tests;

public sealed class DaodanRuntimeDeployerTests
{
    [Fact]
    public void DeployFpsRuntime_copies_the_fps_runtime_files_to_a_valid_installation()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-runtime-{Guid.NewGuid():N}");
        var packagePath = Path.Combine(root, "daodan.zip");
        var installationPath = Path.Combine(root, "Oni");
        Directory.CreateDirectory(installationPath);
        File.WriteAllText(Path.Combine(installationPath, "Oni.exe"), "retail-executable");
        Directory.CreateDirectory(Path.Combine(installationPath, "GameDataFolder"));

        try
        {
            using (var archive = ZipFile.Open(packagePath, ZipArchiveMode.Create))
            {
                WriteEntry(archive, "Oni.exe", "modern-executable");
                WriteEntry(archive, "fps/binkw32.dll", "modern-video-runtime");
                WriteEntry(archive, "fps/realbink.dll", "modern-bink-runtime");
                WriteEntry(archive, "fps/libode_single.dll", "modern-physics-runtime");
            }

            var type = Type.GetType("OniModern.Core.DaodanRuntimeDeployer, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("DeployFpsRuntime", new[] { typeof(string), typeof(string) });
            Assert.NotNull(method);
            _ = method.Invoke(Activator.CreateInstance(type), new object[] { packagePath, installationPath });

            Assert.Equal("modern-executable", File.ReadAllText(Path.Combine(installationPath, "Oni.exe")));
            Assert.Equal("modern-video-runtime", File.ReadAllText(Path.Combine(installationPath, "binkw32.dll")));
            Assert.Equal("modern-bink-runtime", File.ReadAllText(Path.Combine(installationPath, "realbink.dll")));
            Assert.Equal("modern-physics-runtime", File.ReadAllText(Path.Combine(installationPath, "libode_single.dll")));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static void WriteEntry(ZipArchive archive, string entryName, string contents)
    {
        using var writer = new StreamWriter(archive.CreateEntry(entryName).Open());
        writer.Write(contents);
    }
}
