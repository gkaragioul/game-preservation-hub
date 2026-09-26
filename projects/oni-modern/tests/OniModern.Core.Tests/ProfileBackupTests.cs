using Xunit;

namespace OniModern.Core.Tests;

public sealed class ProfileBackupTests
{
    [Fact]
    public void CreateBackup_copies_the_existing_configuration_before_modernization()
    {
        var root = Path.Combine(Path.GetTempPath(), $"oni-modern-backup-{Guid.NewGuid():N}");
        Directory.CreateDirectory(root);
        File.WriteAllText(Path.Combine(root, "daodan.ini"), "original-profile");
        File.WriteAllText(Path.Combine(root, "key_config.txt"), "original-controls");
        File.WriteAllText(Path.Combine(root, "Oni.exe"), "original-executable");
        File.WriteAllText(Path.Combine(root, "binkw32.dll"), "original-video-runtime");
        File.WriteAllText(Path.Combine(root, "persist.dat"), "original-preferences");

        try
        {
            var type = Type.GetType("OniModern.Core.ProfileBackupService, OniModern.Core");
            Assert.NotNull(type);
            var method = type.GetMethod("CreateBackup", new[] { typeof(string), typeof(string) });
            Assert.NotNull(method);

            var backupRoot = Path.Combine(root, "OniModern Backups");
            var createdBackup = Assert.IsType<string>(method.Invoke(Activator.CreateInstance(type), new object[] { root, backupRoot }));

            Assert.Equal("original-profile", File.ReadAllText(Path.Combine(createdBackup, "daodan.ini")));
            Assert.Equal("original-controls", File.ReadAllText(Path.Combine(createdBackup, "key_config.txt")));
            Assert.Equal("original-executable", File.ReadAllText(Path.Combine(createdBackup, "Oni.exe")));
            Assert.Equal("original-video-runtime", File.ReadAllText(Path.Combine(createdBackup, "binkw32.dll")));
            Assert.Equal("original-preferences", File.ReadAllText(Path.Combine(createdBackup, "persist.dat")));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
