using System.IO.Compression;

namespace OniModern.Core;

public sealed class DaodanRuntimeDeployer
{
    public IReadOnlyList<string> DeployFpsRuntime(string packagePath, string installationPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(packagePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);

        var source = Path.GetFullPath(packagePath);
        var destinationRoot = Path.GetFullPath(installationPath);
        var detector = new InstallationDetector();
        if (!detector.Detect(destinationRoot).IsValid)
        {
            throw new InvalidOperationException("The destination must be a valid Oni installation.");
        }

        using var archive = ZipFile.OpenRead(source);
        var entries = archive.Entries
            .Where(IsFpsRuntimeFile)
            .ToArray();

        if (!entries.Any(entry => string.Equals(entry.FullName, "Oni.exe", StringComparison.OrdinalIgnoreCase)))
        {
            throw new InvalidDataException("The Daodan package does not contain its replacement Oni.exe.");
        }

        var deployed = new List<string>();
        foreach (var entry in entries)
        {
            var relativePath = string.Equals(entry.FullName, "Oni.exe", StringComparison.OrdinalIgnoreCase)
                ? "Oni.exe"
                : entry.FullName["fps/".Length..];
            var destination = GetDestinationPath(destinationRoot, relativePath);
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            entry.ExtractToFile(destination, overwrite: true);
            deployed.Add(destination);
        }

        return deployed;
    }

    private static bool IsFpsRuntimeFile(ZipArchiveEntry entry) =>
        !string.IsNullOrEmpty(entry.Name) &&
        (string.Equals(entry.FullName, "Oni.exe", StringComparison.OrdinalIgnoreCase) ||
         entry.FullName.StartsWith("fps/", StringComparison.OrdinalIgnoreCase));

    private static string GetDestinationPath(string destinationRoot, string relativePath)
    {
        var rootWithSeparator = Path.EndsInDirectorySeparator(destinationRoot)
            ? destinationRoot
            : destinationRoot + Path.DirectorySeparatorChar;
        var destination = Path.GetFullPath(Path.Combine(destinationRoot, relativePath));

        if (!destination.StartsWith(rootWithSeparator, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("The Daodan package contains an unsafe file path.");
        }

        return destination;
    }
}
