using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using Forms = System.Windows.Forms;
using OniModern.Core;

namespace OniModern.Launcher;

public partial class MainWindow : Window
{
    private readonly InstallationDetector detector = new();
    private readonly ProfileBackupService backupService = new();
    private readonly DaodanProfileWriter profileWriter = new();
    private readonly DaodanRuntimeDeployer runtimeDeployer = new();
    private readonly PersistSettingsWriter settingsWriter = new();
    private readonly ModernControlsWriter controlsWriter = new();
    private readonly NativeDisplayResolution nativeDisplayResolution = new();

    public MainWindow()
    {
        InitializeComponent();
        StatusTextBlock.Text = "Select an existing Oni folder containing Oni.exe and GameDataFolder.";
    }

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        using var dialog = new Forms.FolderBrowserDialog
        {
            Description = "Select the Oni installation folder",
            UseDescriptionForTitle = true
        };

        if (dialog.ShowDialog() == Forms.DialogResult.OK)
        {
            InstallationPathTextBox.Text = dialog.SelectedPath;
            ValidateInstallation();
        }
    }

    private void Validate_Click(object sender, RoutedEventArgs e) => ValidateInstallation();

    private void ApplyProfile_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);
        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern profile, controls, and native {display.Width}x{display.Height} graphics applied. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }

    private void InstallRuntime_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        var package = FindRuntimePackage();
        if (package is null)
        {
            StatusTextBlock.Text = "The bundled modern runtime package was not found.";
            return;
        }

        var backupRoot = Path.Combine(installation.RootPath, "OniModern Backups");
        var backup = backupService.CreateBackup(installation.RootPath, backupRoot);
        var deployed = runtimeDeployer.DeployFpsRuntime(package, installation.RootPath);
        var profile = profileWriter.WriteModernProfile(installation.RootPath);
        var display = GetNativeDisplayResolution();
        var preferences = settingsWriter.ConfigureModernDisplay(installation.RootPath, display.Width, display.Height);
        var controls = controlsWriter.WriteModernControls(installation.RootPath);
        StatusTextBlock.Text = $"Modern runtime installed ({deployed.Count} files) with modern controls and native {display.Width}x{display.Height} graphics. Backup: {backup}; profile: {profile}; controls: {controls}; preferences: {preferences}";
    }

    private void Launch_Click(object sender, RoutedEventArgs e)
    {
        var installation = ValidateInstallation();
        if (installation is null)
        {
            return;
        }

        Process.Start(new ProcessStartInfo(installation.ExecutablePath)
        {
            WorkingDirectory = installation.RootPath,
            UseShellExecute = true
        });
        StatusTextBlock.Text = "Oni launch requested.";
    }

    private InstallationStatus? ValidateInstallation()
    {
        if (string.IsNullOrWhiteSpace(InstallationPathTextBox.Text))
        {
            StatusTextBlock.Text = "Choose an Oni installation folder first.";
            return null;
        }

        var installation = detector.Detect(InstallationPathTextBox.Text.Trim());
        StatusTextBlock.Text = installation.IsValid
            ? "Valid Oni installation detected."
            : "Not a valid Oni installation: Oni.exe and GameDataFolder must both exist in the selected folder.";
        return installation.IsValid ? installation : null;
    }

    private static string? FindRuntimePackage()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, ".runtime", "runtime", "DaodanDLL.zip");
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }

    private DisplayResolution GetNativeDisplayResolution()
    {
        var screen = Forms.Screen.PrimaryScreen
            ?? throw new InvalidOperationException("No active display was detected.");
        var bounds = screen.Bounds;
        var physicalBounds = PhysicalDesktopMetrics.Read(bounds.Width, bounds.Height);
        return nativeDisplayResolution.Resolve(bounds.Width, bounds.Height, physicalBounds.Width, physicalBounds.Height);
    }

    private static class PhysicalDesktopMetrics
    {
        private const int DesktopVerticalResolution = 117;
        private const int DesktopHorizontalResolution = 118;

        [DllImport("user32.dll")]
        private static extern IntPtr GetDC(IntPtr window);

        [DllImport("user32.dll")]
        private static extern int ReleaseDC(IntPtr window, IntPtr deviceContext);

        [DllImport("gdi32.dll")]
        private static extern int GetDeviceCaps(IntPtr deviceContext, int index);

        public static (int Width, int Height) Read(int fallbackWidth, int fallbackHeight)
        {
            var deviceContext = GetDC(IntPtr.Zero);
            if (deviceContext == IntPtr.Zero)
            {
                return (fallbackWidth, fallbackHeight);
            }

            try
            {
                var width = GetDeviceCaps(deviceContext, DesktopHorizontalResolution);
                var height = GetDeviceCaps(deviceContext, DesktopVerticalResolution);
                return width > 0 && height > 0 ? (width, height) : (fallbackWidth, fallbackHeight);
            }
            finally
            {
                ReleaseDC(IntPtr.Zero, deviceContext);
            }
        }
    }
}
