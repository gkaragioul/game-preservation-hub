$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$htmlPath = Join-Path $repositoryRoot 'index.html'
$html = Get-Content -LiteralPath $htmlPath -Raw

$requiredContent = @(
  'World War 3',
  'Spiral Warrior',
  'Heretic II Apple Silicon',
  'Theme Hospital Apple Silicon',
  'Oni Modern',
  'https://github.com/gkaragioul/ww3-offline-preservation',
  'https://github.com/gkaragioul/spiral-warrior-offline-preservation',
  'https://github.com/gkaragioul/Heretic2_Apple_Silicon',
  'https://github.com/gkaragioul/ThemeHospital_Apple_Silicon',
  'https://github.com/gkaragioul/OniModern'
)

foreach ($item in $requiredContent) {
  if ($html -notlike "*$item*") {
    throw "Missing required public content: $item"
  }
}

if (([regex]::Matches($html, 'class="project-card"')).Count -ne 5) {
  throw 'Expected exactly five project cards.'
}

if ($html -notlike '*no original game files*') {
  throw 'Missing rights boundary.'
}
