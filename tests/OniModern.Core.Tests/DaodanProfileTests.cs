using Xunit;

namespace OniModern.Core.Tests;

public sealed class DaodanProfileTests
{
    [Fact]
    public void WriteModernProfile_creates_borderless_controls_and_modern_graphics_settings()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-profile-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.DaodanProfileWriter, OniModern.Core");
            Assert.NotNull(type);

            var method = type.GetMethod("WriteModernProfile", new[] { typeof(string) });
            Assert.NotNull(method);
            var profilePath = Assert.IsType<string>(method.Invoke(Activator.CreateInstance(type), new object[] { root }));
            var profile = File.ReadAllText(profilePath);

            Assert.Contains("switch = false", profile);
            Assert.Contains("firstpersonfov = 90", profile);
            Assert.Contains("uiscale = medium", profile);
            Assert.Contains("fixsky = true", profile);
            Assert.Contains("daodangl = true", profile);
            Assert.Contains("maxcorpses = 64", profile);
            Assert.Contains("enableODE = true", profile);
            Assert.Contains("border = false", profile);
            Assert.Contains("daodaninput = true", profile);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
