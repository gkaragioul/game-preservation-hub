using Xunit;

namespace OniModern.Core.Tests;

public sealed class NativeDisplayResolutionTests
{
    [Fact]
    public void Resolve_preserves_the_active_display_native_resolution()
    {
        var type = Type.GetType("OniModern.Core.NativeDisplayResolution, OniModern.Core");
        Assert.NotNull(type);

        var resolver = Activator.CreateInstance(type!);
        var method = type!.GetMethod("Resolve", new[] { typeof(int), typeof(int) });
        Assert.NotNull(method);

        var resolution = method!.Invoke(resolver, new object[] { 2560, 1440 });
        Assert.NotNull(resolution);
        Assert.Equal((short)2560, resolution!.GetType().GetProperty("Width")!.GetValue(resolution));
        Assert.Equal((short)1440, resolution.GetType().GetProperty("Height")!.GetValue(resolution));
    }

    [Fact]
    public void Resolve_prefers_physical_metrics_when_windows_scales_logical_pixels()
    {
        var type = Type.GetType("OniModern.Core.NativeDisplayResolution, OniModern.Core");
        Assert.NotNull(type);

        var resolver = Activator.CreateInstance(type!);
        var method = type!.GetMethod("Resolve", new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
        Assert.NotNull(method);

        var resolution = method!.Invoke(resolver, new object[] { 1920, 1080, 2560, 1440 });
        Assert.NotNull(resolution);
        Assert.Equal((short)2560, resolution!.GetType().GetProperty("Width")!.GetValue(resolution));
        Assert.Equal((short)1440, resolution.GetType().GetProperty("Height")!.GetValue(resolution));
    }
}
