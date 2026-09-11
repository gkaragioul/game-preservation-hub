# Game Preservation Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a one-page GitHub Pages catalogue for five selected game preservation and modernization projects.

**Architecture:** A dependency-free static site uses semantic HTML for the content and a single stylesheet for the responsive dark visual system. GitHub Pages deploys the contents of the repository through a minimal Actions workflow after each push to `main`.

**Tech Stack:** HTML5, CSS3, GitHub Pages, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-12-game-preservation-hub-design.md`

## Global Constraints

- Publish a single static page with no JavaScript, database, sign-in, analytics, tracking, downloads, game files, or copied build instructions.
- Include exactly five project cards: World War 3, Spiral Warrior, Heretic II Apple Silicon, Theme Hospital Apple Silicon, and Oni Modern.
- Link each card to its public GitHub repository.
- Clearly state that no original game files, assets, clients, or proprietary content are hosted by the hub.
- Mark the two preservation toolkits as paused and seeking collaborators.
- Keep the page responsive, keyboard-accessible, and readable without JavaScript.
- Publish at `https://gkaragioul.github.io/game-preservation-hub/`.

---

### Task 1: Write the semantic project catalogue

**Files:**
- Create: `index.html`
- Test: `tests/verify-content.ps1`

**Interfaces:**
- Consumes: The project names, statuses, summaries, and repository URLs in the design specification.
- Produces: A standalone semantic HTML page with stable selectors used by the verification script: `#project-grid`, `.project-card`, `.status`, and `#rights-boundary`.

- [ ] **Step 1: Write the content test before the page exists**

```powershell
$html = Get-Content -LiteralPath "$PSScriptRoot/../index.html" -Raw
$required = @(
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
foreach ($value in $required) {
  if ($html -notlike "*$value*") { throw "Missing required public content: $value" }
}
if (([regex]::Matches($html, 'class="project-card"')).Count -ne 5) { throw 'Expected exactly five project cards.' }
if ($html -notlike '*no original game files*') { throw 'Missing rights boundary.' }
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: failure because `index.html` does not yet exist.

- [ ] **Step 3: Create the page with the required semantic structure**

```html
<main>
  <section class="hero" aria-labelledby="page-title">
    <p class="eyebrow">George Karagioules</p>
    <h1 id="page-title">Game Preservation &amp; Modernization</h1>
  </section>
  <section id="project-grid" aria-label="Projects">
    <article class="project-card">
      <p class="status status-paused">Paused — seeking collaborators</p>
      <h2>World War 3 — Offline Preservation Toolkit</h2>
      <a href="https://github.com/gkaragioul/ww3-offline-preservation">View project</a>
    </article>
  </section>
  <aside id="rights-boundary">These projects do not distribute original game files, assets, clients, or proprietary content.</aside>
</main>
```

Create all five complete cards, each with accurate platform/category label, current status, concise summary, and repository link from the specification.

- [ ] **Step 4: Run the content test to verify it passes**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: exit code `0` with no missing-content error.

- [ ] **Step 5: Commit the catalogue**

```bash
git add index.html tests/verify-content.ps1
git commit -m "feat: add preservation project catalogue"
```

### Task 2: Apply the responsive visual system

**Files:**
- Create: `styles.css`
- Modify: `index.html`
- Test: `tests/verify-content.ps1`

**Interfaces:**
- Consumes: The semantic IDs and class names created in Task 1.
- Produces: A dark, responsive, keyboard-accessible presentation where the page remains usable from narrow mobile widths through desktop layouts.

- [ ] **Step 1: Extend the test for the stylesheet and keyboard focus**

```powershell
$css = Get-Content -LiteralPath "$PSScriptRoot/../styles.css" -Raw
foreach ($selector in @('.project-card', '#project-grid', ':focus-visible', '@media')) {
  if ($css -notlike "*$selector*") { throw "Missing responsive/accessibility selector: $selector" }
}
if ($html -notlike '*<link rel="stylesheet" href="styles.css">*') {
  throw 'The page does not load its stylesheet.'
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: failure because the stylesheet and page link do not yet exist.

- [ ] **Step 3: Add the stylesheet and link it from the page**

```css
:root {
  color-scheme: dark;
  --canvas: #0b1017;
  --surface: #121b27;
  --ink: #edf3fb;
  --muted: #a8b6c6;
  --accent: #78d8c8;
}

#project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
}

.project-card { background: var(--surface); }
a:focus-visible { outline: 3px solid var(--accent); outline-offset: 3px; }

@media (max-width: 640px) { main { padding: 1rem; } }
```

Use the token set consistently, preserve readable contrast, provide distinct badges for paused and active/source-project states, and avoid decorative images that do not carry project information.

- [ ] **Step 4: Run the expanded test to verify it passes**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: exit code `0`; all required selectors and page content are present.

- [ ] **Step 5: Commit the visual system**

```bash
git add index.html styles.css tests/verify-content.ps1
git commit -m "feat: style the project hub"
```

### Task 3: Add GitHub Pages deployment and publication documentation

**Files:**
- Create: `.github/workflows/deploy-pages.yml`
- Create: `README.md`
- Modify: `tests/verify-content.ps1`
- Test: `tests/verify-content.ps1`

**Interfaces:**
- Consumes: Static `index.html` and `styles.css` from Tasks 1–2.
- Produces: A GitHub Pages workflow triggered by pushes to `main`, plus concise maintenance instructions.

- [ ] **Step 1: Extend the test for deploy configuration**

```powershell
$workflow = Get-Content -LiteralPath "$PSScriptRoot/../.github/workflows/deploy-pages.yml" -Raw
foreach ($value in @('workflow_dispatch:', 'push:', 'branches: [main]', 'actions/deploy-pages@v4')) {
  if ($workflow -notlike "*$value*") { throw "Missing GitHub Pages workflow setting: $value" }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: failure because the deployment workflow does not yet exist.

- [ ] **Step 3: Create the GitHub Pages workflow**

```yaml
name: Deploy GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: .
      - id: deployment
        uses: actions/deploy-pages@v4
```

Create `README.md` with the public URL, the five linked projects, and one sentence stating that project-specific documentation remains in each repository.

- [ ] **Step 4: Run the complete verification**

Run: `pwsh -NoProfile -File tests/verify-content.ps1`

Expected: exit code `0`.

- [ ] **Step 5: Commit deployment files**

```bash
git add .github/workflows/deploy-pages.yml README.md tests/verify-content.ps1
git commit -m "ci: deploy hub to GitHub Pages"
```

### Task 4: Create the public repository and verify publication

**Files:**
- Modify: GitHub repository settings and GitHub Pages configuration only.

**Interfaces:**
- Consumes: The verified static site and deployment workflow from Tasks 1–3.
- Produces: Public repository `gkaragioul/game-preservation-hub` and the live GitHub Pages URL.

- [ ] **Step 1: Create the public repository and connect the existing local repository**

```bash
gh repo create gkaragioul/game-preservation-hub --public --source . --remote origin --push
```

- [ ] **Step 2: Configure Pages to deploy from GitHub Actions**

```bash
gh api --method POST repos/gkaragioul/game-preservation-hub/pages \
  -H "Accept: application/vnd.github+json" \
  -f build_type=workflow
```

- [ ] **Step 3: Verify the Pages deployment**

```bash
gh api repos/gkaragioul/game-preservation-hub/pages --jq '.html_url'
```

Expected: `https://gkaragioul.github.io/game-preservation-hub/`.

- [ ] **Step 4: Load the published URL and verify the five public repository links**

```bash
curl.exe --fail --location --silent https://gkaragioul.github.io/game-preservation-hub/ | Select-String 'World War 3|Spiral Warrior|Heretic II|Theme Hospital|Oni Modern'
```

Expected: a successful HTTP response containing all five project names.

- [ ] **Step 5: Record publication completion**

```bash
git log -1 --oneline
```

Expected: latest commit corresponds to the static hub deployment configuration.
