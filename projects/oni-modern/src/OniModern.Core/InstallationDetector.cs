namespace OniModern.Core;

public sealed class InstallationDetector
{
    public InstallationStatus Detect(string installationPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);

        var root = Path.GetFullPath(installationPath);
        var executablePath = Path.Combine(root, "Oni.exe");
        var gameDataPath = Path.Combine(root, "GameDataFolder");

        return new InstallationStatus(
            root,
            executablePath,
            gameDataPath,
            File.Exists(executablePath) && Directory.Exists(gameDataPath));
    }
}

public sealed record InstallationStatus(
    string RootPath,
    string ExecutablePath,
    string GameDataPath,
    bool IsValid);
