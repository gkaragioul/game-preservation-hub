from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

PROJECT_MANIFEST = {
    'packageUrl': 'http://127.0.0.1:18080/remote-assets/',
    'remoteManifestUrl': 'http://127.0.0.1:18080/remote-assets/project.manifest',
    'remoteVersionUrl': 'http://127.0.0.1:18080/remote-assets/version.manifest',
    'version': '1.1.0.96-local-en',
    'assets': {},
    'searchPaths': [],
}

VERSION_MANIFEST = {
    'packageUrl': PROJECT_MANIFEST['packageUrl'],
    'remoteManifestUrl': PROJECT_MANIFEST['remoteManifestUrl'],
    'remoteVersionUrl': PROJECT_MANIFEST['remoteVersionUrl'],
    'version': PROJECT_MANIFEST['version'],
}

MANIFEST_PATHS = [
    '/remote-assets/project.manifest',
    '/oversea/remote-assets/project.manifest',
    '/x3-hd/remote-assets/project.manifest',
    '/x3-hd-test/remote-assets/project.manifest',
]
VERSION_PATHS = [
    '/remote-assets/version.manifest',
    '/oversea/remote-assets/version.manifest',
    '/x3-hd/remote-assets/version.manifest',
    '/x3-hd-test/remote-assets/version.manifest',
]

def project_manifest():
    return JSONResponse(PROJECT_MANIFEST)


def version_manifest():
    return JSONResponse(VERSION_MANIFEST)


for path in MANIFEST_PATHS:
    router.add_api_route(path, project_manifest, methods=['GET'])
for path in VERSION_PATHS:
    router.add_api_route(path, version_manifest, methods=['GET'])
