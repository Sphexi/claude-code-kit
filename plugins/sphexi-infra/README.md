# sphexi-infra

Cloud architecture, Kubernetes, Terraform, service mesh and CI/CD pipelines.

Part of [claude-code-kit](https://github.com/sphexi/claude-code-kit) 0.1.0. Licensed MIT.

## Install

```
/plugin marketplace add sphexi/claude-code-kit
/plugin install sphexi-infra@sphexi
```

This plugin has no dependencies.

## What's in it

8 agents, 1 commands and 12 skills from 2 upstream plugins:

- **cloud-infrastructure** — agents: `cloud-infrastructure-cloud-architect`, `cloud-infrastructure-deployment-engineer`, `cloud-infrastructure-kubernetes-architect`, `cloud-infrastructure-network-engineer`, `cloud-infrastructure-terraform-specialist`, `hybrid-cloud-architect`, `service-mesh-expert`; skills: `cost-optimization`, `hybrid-cloud-networking`, `istio-traffic-management`, `linkerd-patterns`, `mtls-configuration`, `multi-cloud-architecture`, `service-mesh-observability`, `terraform-module-library`
- **cicd-automation** — agents: `cicd-automation-devops-troubleshooter`; commands: `workflow-automate`; skills: `deployment-pipeline-design`, `github-actions-templates`, `gitlab-ci-patterns`, `secrets-management`

Agents keep the names their upstream declares, so commands that call them by `subagent_type` resolve unchanged. Commands are invoked as `/sphexi-infra:<command>`.

## Provenance

Each upstream plugin's source repository, pinned commit, local modifications and license are in `notices/<plugin>/UPSTREAM.md` and `notices/<plugin>/LICENSE`. This directory is generated from `claude/vendor/` in the source repository; edit there, not here.
