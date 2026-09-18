# Publication boundary

Public project code, build instructions and reviewed compatibility observations are welcome. Private engine implementation, internal orchestration, private evidence, credentials and workspace exports must stay outside public repositories and downloadable artifacts.

## Before the first public push

Requires Node.js 20 or newer. Install the hook in **each clone** before working:

```sh
git config core.hooksPath .githooks
node tools/check-publication.mjs --staged
```

The pre-push hook inspects outgoing committed file versions, including a secret added and then removed before pushing. It also inspects the outgoing tip. It does not run game code. A new branch needs the existing origin/main reference; fetch it first. Missing refs, unreadable files and inspection limits fail closed.

GitHub's required publication-boundary check inspects proposed history using the **base branch's** checker and exception list. Candidate code is read as data, never executed by this privileged event. Keep main protected, with direct pushes and force pushes disabled. Contributors submit pull requests; maintainers review the changes and any policy edits before merging.

The GitHub check happens **after** a branch or pull request becomes public. It cannot retract an upload. The local hook is the first check; it can be bypassed deliberately and must be installed in every new clone. GitHub secret scanning and push protection provide another layer.

## Releases and website files

Inspect an unpacked staging directory before packaging or uploading it:

```sh
node tools/check-publication.mjs --directory /path/to/public-staging
```

Do not include the repository's .git directory in staging. The guard rejects unreviewed archives and executable artifacts instead of assuming their contents are safe. For source releases, scan the exact Git revision before creating the archive. Manual release uploads still require review; branch protection does not gate GitHub's release upload API.

## Exceptions and limits

Existing public project notes, upstream dependency pins and vendor artifacts may have narrowly scoped entries in tools/publication-exceptions.json. Content exceptions bind a path, SHA-256 and specific rule; changed bytes fail again. Dependency exceptions bind an exact commit and do not recursively certify third-party source. Never add an exception merely to silence a new finding.

Diagnostics report categories and relative paths, not matched credential values. The guard detects common private paths, internal links, credential patterns and selected private-core signatures, including UTF-16 text. It is not a semantic review, malware scanner or proof that arbitrary code is safe to publish. It does not erase historical copies or comprehensively inspect encoded secrets and binaries. Review source, artifacts and changed exceptions before publication.
