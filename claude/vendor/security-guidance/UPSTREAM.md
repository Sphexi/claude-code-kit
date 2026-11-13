# UPSTREAM — `security-guidance`

| Field | Value |
|---|---|
| Plugin | `security-guidance` |
| Upstream marketplace | `claude-plugins-official` |
| Source repo | https://github.com/anthropics/claude-plugins-official |
| Source path | `plugins/security-guidance` |
| Upstream commit | `dceb15d50832e6adf380bedc26dde03d251324b9` |
| Commit provenance | content SHA (`.gcs-sha`; this marketplace is distributed as a GCS snapshot, not a git clone) |
| Upstream version | `2.0.19` |
| Retrieval date | 2026-11-10 |
| Upstream author | Anthropic |
| License | Apache-2.0 (`LICENSE` in this directory) |
| Deployed as | optional extra — installed only with `deploy --extra security-guidance` |

## Contents

- **hooks** (13): `_base.py`, `diffstate.py`, `ensure_agent_sdk.py`, `extensibility.py`, `gitutil.py`, `hooks.json`, `llm.py`, `patterns.py`, `reporesolve.py`, `review_api.py`, `security_reminder_hook.py`, `session_state.py`, `sg-python.sh`

## Stripped on the way in

- `tests/conftest.py`
- `tests/test_add_failure_metric.py`
- `tests/test_agentic_auth_stop.py`
- `tests/test_base_url.py`
- `tests/test_baseline_lookup.py`
- `tests/test_baseline_snapshot.py`
- `tests/test_bootstrap_spawn_cwd.py`
- `tests/test_credential_routing.py`
- `tests/test_custom_headers.py`
- `tests/test_custom_rule_stats.py`
- `tests/test_diff_parsing.py`
- `tests/test_diff_prefix_config.py`
- `tests/test_findings_delivery.py`
- `tests/test_gateway_sign_in.py`
- `tests/test_git_index_locks.py`
- `tests/test_git_program.py`
- `tests/test_inflight_reviews.py`
- `tests/test_interp_reparse_metric.py`
- `tests/test_launcher_alias_own_path.py`
- `tests/test_launcher_newer_python.py`
- `tests/test_launcher_probe_env.py`
- `tests/test_launcher_probe_timing.py`
- `tests/test_launcher_process_count.py`
- `tests/test_launcher_unreadable_script.py`
- `tests/test_nested_repos.py`
- `tests/test_network_failure_class.py`
- `tests/test_no_credentials_notice.py`
- `tests/test_notebook_edit_patterns.py`
- `tests/test_pattern_fired_metrics.py`
- `tests/test_patterns_file_shape.py`
- `tests/test_portable_output.py`
- `tests/test_project_config_files.py`
- `tests/test_project_rules_after_cd.py`
- `tests/test_prompt_cache.py`
- `tests/test_prompt_untracked_snapshot.py`
- `tests/test_repeated_diff_count.py`
- `tests/test_repo_resolution.py`
- `tests/test_review_model.py`
- `tests/test_review_outcomes.py`
- `tests/test_review_session_persistence.py`
- `tests/test_review_usage_log.py`
- `tests/test_reviewer_context_metrics.py`
- `tests/test_reviewer_oauth_token.py`
- `tests/test_reviewer_tools.py`
- `tests/test_sdk_bootstrap_switches.py`
- `tests/test_sdk_emptied_install.py`
- `tests/test_sdk_install_timeout.py`
- `tests/test_secret_named_metric.py`
- `tests/test_secret_renames.py`
- `tests/test_secret_shaped_paths.py`
- `tests/test_slow_prompt_metrics.py`
- `tests/test_state_dir_mode.py`
- `tests/test_state_file.py`
- `tests/test_stop_baseline_checkout.py`
- `tests/test_stop_diff_memory.py`
- `tests/test_stop_finding_no_edit_record.py`
- `tests/test_stop_review_paths.py`
- `tests/test_stop_scope_metrics.py`
- `tests/test_temp_index_cleanup.py`
- `tests/test_tls_store_unreadable_cert.py`
- `tests/test_turn_commits_metric.py`
- `tests/test_unmatched_bash_metric.py`
- `tests/test_untracked_cap.py`
- `tests/test_user_config_dir.py`
- `tests/test_windows_cli_lookup.py`

## Not vendored

Nothing — every upstream component is carried.

## Collapsed into canonical copies

Nothing.

## Local modifications

None. The vendored copy is byte-identical to the upstream repository's content.

## Files added

None.

## Line endings

Text files are normalised to UTF-8 with LF line endings.

## Re-syncing

Run `python tools/vendor_sync.py --apply`. It re-copies from the local marketplace clone and
re-applies every modification listed above from its declared table. It fails rather than
skipping if upstream has changed the text a modification targets.
