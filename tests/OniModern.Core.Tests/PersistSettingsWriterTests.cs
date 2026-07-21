using Xunit;

namespace OniModern.Core.Tests;

public sealed class PersistSettingsWriterTests
{
    [Fact]
    public void ConfigureModernDisplay_sets_high_detail_subtitles_and_a_32_bit_resolution()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        var persistPath = Path.Combine(root, "persist.dat");
        var bytes = new byte[0x60];
        bytes[0x44] = 0x02;
        File.WriteAllBytes(persistPath, bytes);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            method.Invoke(Activator.CreateInstance(type), new object[] { root, (short)1920, (short)1080 });

            var configured = File.ReadAllBytes(persistPath);
            Assert.Equal(4, BitConverter.ToInt32(configured, 0x3C));
            Assert.Equal(3, BitConverter.ToInt32(configured, 0x44));
            Assert.Equal((short)1920, BitConverter.ToInt16(configured, 0x4C));
            Assert.Equal((short)1080, BitConverter.ToInt16(configured, 0x4E));
            Assert.Equal((short)32, BitConverter.ToInt16(configured, 0x50));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public void ConfigureModernDisplay_provisions_a_full_preferences_record_when_the_game_has_not_saved_yet()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            method.Invoke(Activator.CreateInstance(type), new object[] { root, (short)1920, (short)1080 });

            var configured = File.ReadAllBytes(Path.Combine(root, "persist.dat"));
            Assert.Equal(0x60 + (400 * 0x204), configured.Length);
            Assert.Equal((short)1920, BitConverter.ToInt16(configured, 0x4C));
            Assert.Equal((short)1080, BitConverter.ToInt16(configured, 0x4E));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
