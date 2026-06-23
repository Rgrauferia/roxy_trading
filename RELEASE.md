# Release Notes & Changelog

Use this template when preparing a release.

## Release X.Y.Z - YYYY-MM-DD

### Summary
A short one-paragraph summary of the release.

### Highlights
- Item 1: brief description
- Item 2: brief description

### Security fixes
- List any security advisories addressed and their mitigations.

### Full changelog
- PR #123 — Fix: description
- PR #124 — Feature: description

### Upgrade notes
- Runtime: Python >= 3.10 required
- Config: update `requirements.txt` and deployment images

### How to release
1. Update `CHANGELOG.md` with the above notes.
2. Create a tag: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
3. Push tags: `git push origin --tags`
4. Open a GitHub release and attach artifacts if needed.

