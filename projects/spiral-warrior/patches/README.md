# Patching and Redirection Notes

Prefer network/DNS/hosts redirection before modifying APK files.

## Approach 1: rooted emulator hosts file

Use `patches/hosts.example` as a starting point. Replace `127.0.0.1` with the PC host IP reachable from the emulator, commonly `10.0.2.2` on Android Studio Emulator.

## Approach 2: DNS/proxy route

Run local DNS/proxy tooling on the PC and route target hostnames to the local backend/proxy. This avoids changing APK contents.

## Approach 3: future APK config/string patch

Only if runtime evidence shows DNS/proxy is insufficient, patch config files or hardcoded host strings in a reproducible script. Do not modify original APK/XAPK files in place. Work from copies and document every byte-level change.

## Target hostnames

See `patches/hosts.example`.
