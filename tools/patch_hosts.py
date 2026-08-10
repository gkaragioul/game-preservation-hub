#!/usr/bin/env python3
"""Generate local hosts-file entries for Spiral Warrior endpoint redirection.
This does not patch APKs. It prints entries a developer may apply to a rooted emulator, test DNS, or proxy config.
"""
from pathlib import Path
HOSTS = [
    'sdk-login-cocooversea.17m3.com',
    'sdk-package-update-config.17m3.com',
    'ups-config.17m3.com',
    'sdk-heartbeat.17m3.com',
    'cdnsgp-x3jl-release.17m3.com',
    'cdn-spinarena.17m3.com',
    'lxys-area.17m3.com',
    'lxys-audit-area.17m3.com',
    'lxys-test-area.17m3.com',
    'lxys1-client.17m3.com',
]

def main():
    ip='127.0.0.1'
    print('# Spiral Warrior local redirection entries')
    print('# Replace 127.0.0.1 with the host IP reachable from the emulator if needed.')
    for h in HOSTS:
        print(f'{ip}\t{h}')

if __name__ == '__main__':
    main()
