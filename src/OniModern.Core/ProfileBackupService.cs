namespace OniModern.Core;

public sealed class ProfileBackupService
{
    private static readonly string[] ManagedFiles =
    [
        "Oni.exe",
        "binkw32.dll",
        "realbink.dll",
        "libgcc_s_dw2-1.dll",
        "libode_single.dll",
        "libssp-0.dll",
        "libstdc++-6.dll",
        "libwinpthread-1.dll",
        "daodan.ini",
        "key_config.txt",
        "persist.dat"
    ];

    public string CreateBackup(string installationPath, string backupRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(backupRoot);

        var sourceRoot = Path.GetFullPath(installationPath);
        var destination = Path.Combine(
            Path.GetFullPath(backupRoot),
            $"profile-{DateTimeOffset.UtcNow:yyyyMMdd-HHmmss-fff}");

        Directory.CreateDirectory(destination);

        foreach (var fileName in ManagedFiles)
        {
            var source = Path.Combine(sourceRoot, fileName);
            if (File.Exists(source))
            {
                File.Copy(source, Path.Combine(destination, fileName));
            }
        }

        return destination;
    }
}
