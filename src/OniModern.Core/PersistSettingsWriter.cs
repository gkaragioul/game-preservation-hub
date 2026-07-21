namespace OniModern.Core;

public sealed class PersistSettingsWriter
{
    private const int HeaderSize = 0x60;
    private const int SavePointCount = 400;
    private const int SavePointSize = 0x204;

    public string ConfigureModernDisplay(string installationPath, short width, short height)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);
        if (width < 640 || height < 480)
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Oni requires a resolution of at least 640x480.");
        }

        var persistPath = Path.Combine(Path.GetFullPath(installationPath), "persist.dat");
        var bytes = File.Exists(persistPath)
            ? File.ReadAllBytes(persistPath)
            : new byte[HeaderSize + (SavePointCount * SavePointSize)];
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
