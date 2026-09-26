namespace OniModern.Core;

public sealed class ModernControlsWriter
{
    public string WriteModernControls(string installationPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);

        var controlsPath = Path.Combine(Path.GetFullPath(installationPath), "key_config.txt");
        var controls = """
            unbindall

            bind w to forward
            bind a to stepleft
            bind s to backward
            bind d to stepright
            bind mousebutton1 to fire1
            bind mousebutton2 to fire2
            bind mousebutton3 to fire3
            bind mousexaxis to aim_LR
            bind mouseyaxis to aim_UD

            bind leftshift to sprint
            bind leftcontrol to crouch
            bind space to jump
            bind e to action
            bind g to drop
            bind q to swap
            bind r to reload
            bind f to punch
            bind c to kick
            bind tab to hypo
            bind v to lookmode
            bind fkey1 to pausescreen
            bind fkey13 to screenshot
            """;

        File.WriteAllText(controlsPath, controls.Replace("\n", Environment.NewLine));
        return controlsPath;
    }
}
