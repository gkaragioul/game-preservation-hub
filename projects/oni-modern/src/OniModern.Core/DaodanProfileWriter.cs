namespace OniModern.Core;

public sealed class DaodanProfileWriter
{
    public string WriteModernProfile(string installationPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(installationPath);

        var profilePath = Path.Combine(Path.GetFullPath(installationPath), "daodan.ini");
        var profile = """
            # Managed by OniModern. Adjust only through the launcher to preserve a reversible profile.
            [gameplay]
            firstpersonmode = false
            firstpersonfov = 90
            bindablesprint = true
            disabledoubletapsprint = false
            fixconkick = true
            weaponstay = true
            reldropammo = true

            [graphics]
            daodangl = true
            fixsky = true
            visibleholster = true
            bloodyscreen = true
            uiscale = medium
            subtscale = medium
            maxcorpses = 64

            [oni]
            debugfiles = true
            switch = false
            checkpoint_saves = true
            newthrowlogic = true
            throwcheckforwalls = true

            [windows]
            border = false
            daodaninput = true
            directinput = true
            alttab = true
            mousesensitivity = 1.0

            [ode]
            enableODE = true
            ODEthreads = 0
            collideragdolls = true
            selfcollideragdolls = true
            odeusequadtreespace = true
            odedoublestep = true
            ragdollcorpses = true
            """;

        File.WriteAllText(profilePath, profile.Replace("\n", Environment.NewLine));
        return profilePath;
    }
}
