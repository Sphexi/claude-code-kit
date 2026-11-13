# claude-code-kit

> Agents, skills, output styles and curated third-party plugins for Claude Code, installable as a plugin marketplace or deployed into an existing `~/.claude`.

## What It Does

claude-code-kit packages a set of Claude Code subagents, skills, slash commands and output styles into eight plugins. A plugin marketplace named `sphexi` serves them, so you install only the ones you want. A clone-and-deploy path writes the same content into your Claude Code configuration directory, together with a global `CLAUDE.md` and a conservative `settings.json` that a plugin cannot carry.

Most of the content is third-party plugins vendored at pinned commits, grouped into bundles by topic, with every upstream license and local modification recorded. The kit adds thirteen specialist agents, three skills, three output styles, and comment and test standards that reach the main session and every subagent.

Linux, macOS and Windows are supported for clone-and-deploy. The marketplace path needs only Claude Code.

## Install from the marketplace

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-core@sphexi
```

Details, dependencies and updates: [docs/install-marketplace.md](docs/install-marketplace.md).

## Clone and deploy

Requires Python 3.12 or newer.

```bash
git clone https://github.com/sphexi/claude-code-kit.git
cd claude-code-kit
./deploy.sh            # dry run: lists every file it would write
./deploy.sh --apply    # write
```

```powershell
git clone https://github.com/sphexi/claude-code-kit.git
cd claude-code-kit
.\deploy.ps1           # dry run
.\deploy.ps1 --apply   # write
```

Deploy writes nothing without `--apply`, merges into an existing `settings.json`, and never overwrites a file it did not write unless you pass `--overwrite`. See [docs/deploy.md](docs/deploy.md).

## Plugins

| Plugin | Contents |
|---|---|
| `sphexi-core` | Thirteen specialist subagents, four skills, three terseness output styles, and a session-start hook for the code standards |
| `sphexi-review` | Code review, refactoring, testing and debugging agents and commands; feature-dev workflow; TDD cycle; accessibility audits |
| `sphexi-security` | SAST, threat modelling, compliance checks, API and frontend hardening, dependency audits |
| `sphexi-python` | `python-pro`, FastAPI and Django agents, Python pattern skills, project scaffolding |
| `sphexi-languages` | Bash and POSIX shell, Go, and general developer skills |
| `sphexi-backend` | Backend architecture, API scaffolding, database design and migrations, full-stack feature orchestration |
| `sphexi-infra` | Cloud architecture, Kubernetes, Terraform, service mesh, CI/CD pipelines |
| `sphexi-ai` | LLM application development: RAG, embeddings, vector search, prompt engineering, evaluation |
| `twingate-assistant` | Twingate zero trust network access; maintained in its own repository and listed here as an external entry |

Full catalogue: every agent, command, skill, output style and hook, and where each comes from (origin, upstream plugin, repository, license): [docs/plugins.md](docs/plugins.md).

## Documentation

Using the kit:

- [Install from the marketplace](docs/install-marketplace.md)
- [Clone and deploy](docs/deploy.md), with platform pages for [Linux](docs/deploy-linux.md), [macOS](docs/deploy-macos.md) and [Windows](docs/deploy-windows.md)
- [Plugin catalogue](docs/plugins.md) (generated): every agent, command and skill, and where each comes from
- [Settings](docs/settings.md)
- [Terseness and code standards](docs/terseness-and-standards.md)
- [Cowork](docs/cowork.md)
- [Troubleshooting](docs/troubleshooting.md)

Changing and maintaining the kit:

- [Customizing and forking](docs/customizing.md)
- [Vendored upstreams](docs/vendored-upstreams.md)
- [Architecture](docs/architecture.md)
- [Contributing](docs/contributing.md)
- [Releasing](docs/releasing.md)

[CHANGELOG.md](CHANGELOG.md) records released versions. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) lists every third-party source and license.

## License

MIT. See [LICENSE](LICENSE). Vendored plugins keep their own licenses (MIT and Apache-2.0); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
