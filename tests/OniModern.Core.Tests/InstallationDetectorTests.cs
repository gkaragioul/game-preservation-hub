using Xunit;

namespace OniModern.Core.Tests;

public sealed class InstallationDetectorTests
{
    [Fact]
    public void Detect_reports_a_valid_installation_when_Oni_executable_and_game_data_are_present()
    {
        var temporaryRoot = Path.Combine(Path.GetTempPath(), $"oni-modern-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(Path.Combine(temporaryRoot, "GameDataFolder"));
        File.WriteAllText(Path.Combine(temporaryRoot, "Oni.exe"), string.Empty);

        try
        {
            var type = Type.GetType("OniModern.Core.InstallationDetector, OniModern.Core");
            Assert.NotNull(type);

            var method = type.GetMethod("Detect", new[] { typeof(string) });
            Assert.NotNull(method);

            var result = method.Invoke(Activator.CreateInstance(type), new object[] { temporaryRoot });
            Assert.NotNull(result);
            Assert.True((bool)result.GetType().GetProperty("IsValid")!.GetValue(result)!);
            Assert.Equal(Path.Combine(temporaryRoot, "Oni.exe"), result.GetType().GetProperty("ExecutablePath")!.GetValue(result));
        }
        finally
        {
            Directory.Delete(temporaryRoot, recursive: true);
        }
    }
}
