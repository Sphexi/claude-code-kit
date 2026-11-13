# Cowork

Each marketplace plugin is also published as a zip that can be uploaded to Cowork. The zips are built from the committed `plugins/` tree, so their content matches the marketplace.

## Which zips

One zip per plugin, named `claude-code-kit-<plugin>-<version>.zip`, for example `claude-code-kit-sphexi-core-0.1.0.zip`. There are eight: `sphexi-core`, `sphexi-review`, `sphexi-security`, `sphexi-python`, `sphexi-languages`, `sphexi-backend`, `sphexi-infra` and `sphexi-ai`. The external marketplace entry is not zipped; it lives in its own repository.

Upload `sphexi-core` first, then the others you want. Respect the dependencies listed in [install-marketplace.md](install-marketplace.md#dependencies): `sphexi-review` needs `sphexi-security`, and `sphexi-backend` needs `sphexi-infra`, `sphexi-review` and `sphexi-security`.

Every zip except core is the plugin directory unchanged.

## What the core zip adds

Cowork has no output-style mechanism and no global `CLAUDE.md`, so the core zip carries the plugin tree plus:

- `skills/terseness/`: a skill that switches terseness level mid-session. Its `levels/` directory holds `terse-low.md`, `terse-medium.md` and `terse-full.md`, derived from the output styles.

The result is that a Cowork session starts at `terse-full` with the code standards applied, and the `terseness` skill changes the level on request: "terse low", "terse medium", "terse full" or "normal". The register rules do not change with the level. See [terseness-and-standards.md](terseness-and-standards.md).

## Where to download

Each tagged release on the repository's GitHub Releases page has all eight zips attached. The release workflow builds them only when the tag matches the version in `build/kit.json`; see [releasing.md](releasing.md).

## Build the zips yourself

```bash
python build/build_plugins.py --zip
```

The command first checks that the committed generated files are current and refuses to build if they are not. Zips land in `dist/`.

| Option | Effect |
|---|---|
| `--output-dir DIR` | Write the zips to `DIR` instead of `dist/` |
| `--bundle NAME` | Build only that plugin. Repeatable |
| `--version X.Y.Z` | Assert the version. It must equal `build/kit.json`; a leading `v` is ignored. The zip is always named for the committed version |

Zips are reproducible: entries are sorted, timestamps are fixed and file modes are normalised, so building twice from the same tree gives identical bytes.

The build fails if any plugin has a top-level `bin/` directory, which Cowork refuses.
