"""Which vendored plugin ships in which marketplace plugin."""

from __future__ import annotations

from dataclasses import dataclass

CORE = "sphexi-core"


@dataclass(frozen=True)
class Bundle:
    """One generated marketplace plugin and the vendored plugins merged into it."""

    name: str
    description: str
    plugins: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    category: str = ""
    tags: tuple[str, ...] = ()


BUNDLES: tuple[Bundle, ...] = (
    Bundle(
        CORE,
        "Thirteen specialist subagents; the systematic-debugging, code-comments, "
        "test-discipline and skill-creator skills; three terseness output styles; and a "
        "session-start hook that applies the comment and test standards.",
        ("skill-creator",),
        category="workflow",
        tags=("agents", "skills", "output-styles", "code-standards"),
    ),
    Bundle(
        "sphexi-review",
        "Code review, refactoring, testing and debugging: multi-perspective review, PR review "
        "agents, feature-dev workflow, TDD cycle, unit testing and accessibility audits.",
        ("comprehensive-review", "pr-review-toolkit", "feature-dev", "tdd-workflows",
         "unit-testing", "code-refactoring", "code-documentation", "git-pr-workflows",
         "performance-testing-review", "debugging-toolkit", "accessibility-compliance"),
        depends_on=("sphexi-security",),
        category="code-review",
        tags=("review", "testing", "tdd", "refactoring", "debugging", "accessibility"),
    ),
    Bundle(
        "sphexi-security",
        "Security review: SAST, threat modelling, compliance checks, API and frontend "
        "hardening, dependency audits.",
        ("security-scanning", "security-compliance", "backend-api-security",
         "frontend-mobile-security", "dependency-management"),
        category="security",
        tags=("security", "sast", "threat-modeling", "compliance", "dependencies"),
    ),
    Bundle(
        "sphexi-python",
        "Modern Python: python-pro, FastAPI and Django agents plus Python pattern skills.",
        ("python-development",),
        category="language",
        tags=("python", "fastapi", "django"),
    ),
    Bundle(
        "sphexi-languages",
        "Bash and POSIX shell, Go, and general developer skills (git, error handling, auth, "
        "SQL, e2e testing).",
        ("shell-scripting", "systems-programming", "developer-essentials"),
        category="language",
        tags=("bash", "shell", "go", "git", "sql"),
    ),
    Bundle(
        "sphexi-backend",
        "Backend architecture, API scaffolding, database design and migrations, and "
        "full-stack feature orchestration.",
        ("backend-development", "api-scaffolding", "database-design", "database-migrations",
         "full-stack-orchestration"),
        depends_on=("sphexi-infra", "sphexi-review", "sphexi-security"),
        category="backend",
        tags=("backend", "api", "database", "migrations", "architecture"),
    ),
    Bundle(
        "sphexi-infra",
        "Cloud architecture, Kubernetes, Terraform, service mesh and CI/CD pipelines.",
        ("cloud-infrastructure", "cicd-automation"),
        category="infrastructure",
        tags=("cloud", "kubernetes", "terraform", "cicd"),
    ),
    Bundle(
        "sphexi-ai",
        "LLM application development: RAG, embeddings, vector search, prompt engineering "
        "and LLM evaluation.",
        ("llm-application-dev",),
        category="ai",
        tags=("llm", "rag", "embeddings", "prompt-engineering"),
    ),
)

#: Vendored plugins that ship in no marketplace plugin; deploy installs them only on request.
EXTRAS: dict[str, str] = {
    "pyright-lsp": "needs a pyright-langserver binary on the host",
    "security-guidance": "its hooks call the Agent SDK and a host Python",
}

#: Agent types always available, so a reference to them needs no bundle.
BUILTIN_AGENTS = frozenset({"general-purpose", "Explore", "Plan"})


def bundle_names() -> tuple[str, ...]:
    """Return every bundle name in table order."""
    return tuple(b.name for b in BUNDLES)


def get_bundle(name: str) -> Bundle:
    """Return the bundle called `name`, or raise ``KeyError``."""
    for bundle in BUNDLES:
        if bundle.name == name:
            return bundle
    raise KeyError(name)


def bundle_of(plugin: str) -> str | None:
    """Return the bundle that carries a vendored plugin, or ``None`` for an extra."""
    for bundle in BUNDLES:
        if plugin in bundle.plugins:
            return bundle.name
    return None
