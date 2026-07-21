using Xunit;

namespace OniModern.Core.Tests;

public sealed class ModernControlsWriterTests
{
    [Fact]
    public void WriteModernControls_creates_wasd_mouse_sprint_and_interaction_bindings()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-controls-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.ModernControlsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("WriteModernControls", new[] { typeof(string) });
            Assert.NotNull(method);
            var path = Assert.IsType<string>(method.Invoke(Activator.CreateInstance(type), new object[] { root }));
            var controls = File.ReadAllText(path);

            Assert.Contains("bind w to forward", controls);
            Assert.Contains("bind mousebutton1 to fire1", controls);
            Assert.Contains("bind leftshift to sprint", controls);
            Assert.Contains("bind leftcontrol to crouch", controls);
            Assert.Contains("bind e to action", controls);
            Assert.Contains("bind g to drop", controls);
            Assert.Contains("bind r to reload", controls);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
