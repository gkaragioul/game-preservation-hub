namespace OniModern.Core;

public sealed class PersistSettingsWriter
{
    private const int HeaderSize = 0x60;

    public string ConfigureModernDisplay(string installationPath, short width, short height)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);
        if (width < 640 || height < 480)
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Oni requires a resolution of at least 640x480.");
        }

        var persistPath = Path.Combine(Path.GetFullPath(installationPath), "persist.dat");
        if (!File.Exists(persistPath))
        {
            throw new FileNotFoundException(
                "persist.dat does not exist yet. Launch Oni.exe once and quit from the main menu so " +
                "the game can write its own preferences file, then apply the profile again. A file " +
                "synthesized from scratch is not trusted by Oni's own startup code and can crash " +
                "Daodan's OpenGL initialization instead of just falling back to a default resolution.",
                persistPath);
        }

        var bytes = File.ReadAllBytes(persistPath);
        if (bytes.Length < HeaderSize)
        {
            throw new InvalidDataException("persist.dat does not contain Oni's preferences header.");
        }

        BitConverter.TryWriteBytes(bytes.AsSpan(0x3C, sizeof(int)), 4);
        var flags = BitConverter.ToInt32(bytes, 0x44) | 0x01;
        BitConverter.TryWriteBytes(bytes.AsSpan(0x44, sizeof(int)), flags);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x4C, sizeof(short)), width);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x4E, sizeof(short)), height);
        BitConverter.TryWriteBytes(bytes.AsSpan(0x50, sizeof(short)), (short)32);
        File.WriteAllBytes(persistPath, bytes);
        return persistPath;
    }
}
