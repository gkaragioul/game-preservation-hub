# Compatibility data

RLabs compatibility reports are small, evidence-led JSON documents. They record what software was tested, the environment, the observed result, and the source for that conclusion. They are not a promise that every installation will behave the same way.

## Layout

- [`schema.json`](schema.json) defines the report format using JSON Schema draft 2020-12.
- [`records/`](records/) holds one report per tested software and environment combination.

## Status values

| Status | Meaning |
| --- | --- |
| `working` | The documented target flow works in the stated environment. |
| `partial` | Some meaningful flow works, with listed limitations. |
| `blocked` | A specific blocker prevents the documented target flow. |
| `research` | Investigation is active; this is not a compatibility claim. |
| `untested` | The report is a prepared record with no result yet. |

Use a new record when the title, version, operating system, or architecture materially changes. Keep assertions narrow, link evidence, and never add proprietary executables, dumps, credentials, keys, or game assets.

To run the repository's lightweight data check:

```powershell
pwsh -NoProfile -File tests/verify-compatibility.ps1
```
