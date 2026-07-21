namespace OniModern.Core;

public readonly record struct DisplayResolution(short Width, short Height);

public sealed class NativeDisplayResolution
{
    public DisplayResolution Resolve(int logicalWidth, int logicalHeight, int physicalWidth, int physicalHeight)
    {
        return physicalWidth > 0 && physicalHeight > 0
            ? Resolve(physicalWidth, physicalHeight)
            : Resolve(logicalWidth, logicalHeight);
    }

    public DisplayResolution Resolve(int width, int height)
    {
        if (width is < 640 or > short.MaxValue)
        {
            throw new ArgumentOutOfRangeException(nameof(width), "Display width must fit in Oni's graphics preferences.");
        }

        if (height is < 480 or > short.MaxValue)
        {
            throw new ArgumentOutOfRangeException(nameof(height), "Display height must fit in Oni's graphics preferences.");
        }

        return new DisplayResolution((short)width, (short)height);
    }
}
