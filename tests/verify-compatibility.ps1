$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$schemaPath = Join-Path $repositoryRoot 'compatibility/schema.json'
$recordsDirectory = Join-Path $repositoryRoot 'compatibility/records'

if (-not (Test-Path -LiteralPath $schemaPath)) {
    throw "Missing compatibility schema: $schemaPath"
}

$schema = Get-Content -LiteralPath $schemaPath -Raw | ConvertFrom-Json
if ($schema.'$schema' -ne 'https://json-schema.org/draft/2020-12/schema') {
    throw 'The compatibility schema must use JSON Schema draft 2020-12.'
}

$records = Get-ChildItem -LiteralPath $recordsDirectory -Filter '*.json' -File
if ($records.Count -lt 4) {
    throw 'Expected at least four initial compatibility records.'
}

foreach ($recordFile in $records) {
    if (-not (Test-Json -Path $recordFile.FullName -SchemaFile $schemaPath)) {
        throw "Schema validation failed: $($recordFile.Name)."
    }
    $record = Get-Content -LiteralPath $recordFile.FullName -Raw | ConvertFrom-Json
    foreach ($property in @('id', 'software', 'environment', 'assessment', 'evidence')) {
        if ($null -eq $record.$property) {
            throw "Missing $property in $($recordFile.Name)."
        }
    }
    if ($record.assessment.status -notin @('working', 'partial', 'blocked', 'research', 'untested')) {
        throw "Invalid assessment status in $($recordFile.Name)."
    }
}

foreach ($documentationPath in @('CONTRIBUTING.md', 'docs/rlabs-scan-v0.1.md')) {
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot $documentationPath))) {
        throw "Missing public documentation: $documentationPath"
    }
}

$rootReadme = Get-Content -LiteralPath (Join-Path $repositoryRoot 'README.md') -Raw
if ($rootReadme -notmatch 'RLabs') {
    throw 'The root README must position RLabs.'
}
if ($rootReadme -notmatch 'https://github.com/gkaragioul/rlabs-scan') {
    throw 'The root README must link to the rlabs-scan repository.'
}

Write-Output "Validated $($records.Count) compatibility records."
