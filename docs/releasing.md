# Releasing

A release is a version bump, a regeneration, a changelog entry and a tag. The version in `build/kit.json` is the single version of the kit: it is stamped into every generated `plugin.json`, and marketplace users receive an update only when it changes.

## Steps

1. Edit `version` in `build/kit.json`.

2. Regenerate everything that carries the version:

   ```bash
   python build/inline_shared.py
   python build/build_plugins.py
   ```

   This rewrites each `plugins/sphexi-<name>/.claude-plugin/plugin.json`, the plugin READMEs, `.claude-plugin/marketplace.json` and `docs/plugins.md`.

3. Check that nothing is stale:

   ```bash
   python build/inline_shared.py --check
   python build/build_plugins.py --check
   ```

4. Add an entry to `CHANGELOG.md` under the new version, in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Move anything under `## [Unreleased]` into it and give it the release date.

5. Run the fast suite, and the slow suite if deploy, refresh, the wrappers or settings changed:

   ```bash
   python -m pytest tests/python -q
   python -m pytest tests/python -q -m slow
   ```

6. Commit the source and generated changes together and merge to `main`. CI must pass.

7. A maintainer tags the merged commit `vX.Y.Z`, matching the version in `build/kit.json` with a leading `v`, and pushes the tag.

## What the release workflow does

`.github/workflows/release.yml` runs on tags matching `v*`.

The build job has read-only permissions. It runs `python build/inline_shared.py --check` and `python build/build_plugins.py --check`, and fails if the tag with its leading `v` removed differs from the version in `build/kit.json`. It then runs `python build/build_plugins.py --zip --version "$GITHUB_REF_NAME"`, which builds the eight Cowork zips and itself refuses a version that differs from `build/kit.json`, and uploads the zips as a workflow artifact.

The release job has `contents: write`. It downloads the artifact and attaches the zips to a GitHub release for the tag, failing if any expected file is missing.

A tag that does not match the committed version never produces a release. Fix the version or tag and try again.

## What users see

- Marketplace users get the new plugin versions the next time they update the `sphexi` marketplace or when auto-update runs. See [install-marketplace.md](install-marketplace.md#updates).
- Clone-and-deploy users pull the new commit and run `./refresh.sh`. See [deploy.md](deploy.md#refresh).
- Cowork users download the zips from the release. See [cowork.md](cowork.md).

Without a version bump, changes on `main` reach clone-and-deploy users on their next pull but not marketplace users.
