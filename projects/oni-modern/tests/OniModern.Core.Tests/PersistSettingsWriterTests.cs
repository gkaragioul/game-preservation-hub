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
    public void ConfigureModernDisplay_throws_when_persist_dat_does_not_exist_yet()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-persist-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);

        try
        {
            var type = Type.GetType("OniModern.Core.PersistSettingsWriter, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("ConfigureModernDisplay", new[] { typeof(string), typeof(short), typeof(short) });
            Assert.NotNull(method);
            var instance = Activator.CreateInstance(type);

            var invocation = Assert.Throws<System.Reflection.TargetInvocationException>(
                () => method.Invoke(instance, new object[] { root, (short)1920, (short)1080 }));

            Assert.IsType<FileNotFoundException>(invocation.InnerException);
            Assert.False(File.Exists(Path.Combine(root, "persist.dat")));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
