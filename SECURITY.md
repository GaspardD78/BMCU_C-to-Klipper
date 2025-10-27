# Security Policy

## Supported Versions

Use this section to tell people about which versions of your project are
currently being supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 5.1.x   | :white_check_mark: |
| 5.0.x   | :x:                |
| 4.0.x   | :white_check_mark: |
| < 4.0   | :x:                |

## Reporting a Vulnerability

Use this section to tell people how to report a vulnerability.

Tell them where to go, how often they can expect to get an update on a
reported vulnerability, what to expect if the vulnerability is accepted or
declined, etc.

## Repository Artifact Policy

To prevent accidental disclosure of sensitive firmware builds or cached
artefacts, every pull request is scanned for oversized files and forbidden
paths.

### Local checks

Use the helper script before opening a pull request:

```bash
python3 ci/check_repo_artifacts.py \
  --threshold-mb 50 \
  --forbidden-config ci/forbidden-paths.txt
```

- `--threshold-mb` defines the maximum allowed file size (in megabytes).
- `--forbidden-config` points to the list of glob patterns that must never be
  committed.
- Additional temporary patterns can be provided with `--forbidden` arguments.

The script logs in `logs/artifact_guard.log` (rotating at 5 MB with four
backups) and returns a non-zero exit code when policy violations are detected.

### Continuous integration

The **Artifact policy guard** workflow runs on every push to `main` and on all
pull requests. The workflow fails when the repository contains forbidden files
so reviewers are alerted before merging. The workflow configuration is stored
in [`.github/workflows/artifact-guard.yml`](.github/workflows/artifact-guard.yml).
