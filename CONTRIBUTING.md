# Contributing to RLabs

Thank you for making compatibility and preservation knowledge more durable. Contributions should help someone else reproduce an observation without requiring you to share software, private research, personal data, or proprietary content.

## What to contribute

- Test a lawfully obtained copy of software in a clearly described environment.
- Add or improve a compatibility report in [`compatibility/records/`](compatibility/records/).
- Submit a narrowly scoped source fix, build fix, launcher improvement, or documentation correction for a public project.
- Share repeatable dependency, runtime, installer, or configuration knowledge.

## Compatibility reports

1. Read [`compatibility/README.md`](compatibility/README.md) and use [`compatibility/schema.json`](compatibility/schema.json).
2. Create one JSON file per material software-and-environment combination.
3. State exactly what flow you tested. Prefer `partial` or `research` over a broad claim when evidence is limited.
4. Link a public, stable source for the observation: a project README, issue, release note, test log with secrets removed, or reproducible steps.
5. Include known issues and workarounds only when you personally verified them or can cite their source.

Run the check before opening a pull request:

```powershell
pwsh -NoProfile -File tests/verify-compatibility.ps1
```

## Fixes and documentation

- Keep pull requests focused on one issue or one report family.
- Explain the environment, observed behavior, and how you verified the change.
- Do not bundle unrelated formatting or generated-file changes.
- Preserve existing license, attribution, and project-specific contribution rules.

## Boundaries

Do not contribute game files, proprietary assets, commercial clients, decrypted source, keys, credentials, account data, personal data, or bypasses for access controls. Do not upload packet captures or logs that contain tokens, account identifiers, or other private information. RLabs is for lawful compatibility, recovery, and preservation research.
