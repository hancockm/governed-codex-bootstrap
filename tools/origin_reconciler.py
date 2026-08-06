"""Inspect and reconcile project owner branches against ``origin/master``.

The inspection, inbox, and closeout commands are evidence-only apart from an
optional fetch. The only command that changes a working tree is the Core-only
``sync-main`` operation, which accepts a clean, behind-only primary ``master``
and executes ``git merge --ff-only origin/master``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONFIG_SCHEMA_VERSION = "git_reconciliation_config_v1"
REPORT_SCHEMA_VERSION = "git_reconciliation_report_v1"
INBOX_SCHEMA_VERSION = "git_integration_inbox_v1"
CLOSEOUT_SCHEMA_VERSION = "git_reconciliation_closeout_v1"
SYNC_SCHEMA_VERSION = "git_reconciliation_sync_v1"
DEFAULT_CONFIG_RELATIVE = Path("configs/git_reconciliation_v1.json")
TERMINAL_DISPOSITIONS = frozenset({"landed", "superseded"})
KNOWN_DISPOSITIONS = frozenset(
    {"landed", "awaiting_named_integrator", "superseded"}
)


class ReconciliationError(RuntimeError):
    """Raised when repository evidence cannot support a requested operation."""


class InspectionError(ReconciliationError):
    """Raised when a Git or filesystem inspection fails closed."""


class SafetyError(ReconciliationError):
    """Raised when a mutating operation fails a safety precondition."""


@dataclass(frozen=True)
class RoleConfig:
    """Configured branch prefixes for one agent role."""

    name: str
    display_name: str
    strict_prefixes: tuple[str, ...]
    legacy_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class ReconciliationConfig:
    """Versioned owner and canonical-target configuration."""

    schema_version: str
    canonical_remote: str
    canonical_branch: str
    worktree_root: str
    protected_branches: tuple[str, ...]
    agent_aliases: Mapping[str, str]
    roles: Mapping[str, RoleConfig]
    ambiguous_prefixes: tuple[str, ...]

    @property
    def target_ref(self) -> str:
        """Return the configured remote-tracking target reference."""

        return f"{self.canonical_remote}/{self.canonical_branch}"

    def normalize_agent(self, agent: str) -> str:
        """Resolve an agent label or configured alias to a canonical role."""

        normalized = agent.strip().lower()
        normalized = self.agent_aliases.get(normalized, normalized)
        if normalized not in self.roles:
            choices = ", ".join(sorted(self.roles))
            raise ReconciliationError(
                f"unknown agent {agent!r}; configured roles: {choices}"
            )
        return normalized


@dataclass(frozen=True)
class OwnerEvidence:
    """Branch owner classification derived only from versioned configuration."""

    owner: str
    confidence: str
    matched_prefix: str


@dataclass(frozen=True)
class PatchMapping:
    """Stable patch-id mapping from one branch commit to a target commit."""

    source_commit: str
    patch_id: str
    target_commit: str


@dataclass(frozen=True)
class UnmappedCommit:
    """A branch-only commit that lacks an unambiguous patch replacement."""

    source_commit: str
    reason: str
    candidate_target_commits: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorktreeInspection:
    """Safe status and operation evidence for one registered worktree."""

    path: str
    head: str
    branch: str
    is_primary: bool
    status: str
    clean: bool | None
    operations: tuple[str, ...]
    location_state: str


@dataclass(frozen=True)
class PhysicalWorktreeEntry:
    """One immediate physical child of the configured worktree directory."""

    path: str
    kind: str
    registered: bool


@dataclass(frozen=True)
class BranchInspection:
    """Reachability, publication, ownership, and worktree evidence for a branch."""

    branch: str
    owner: str
    owner_confidence: str
    owner_prefix: str
    local_head: str
    remote_head: str
    upstream: str
    publication_state: str
    published_contains_local_head: bool
    inspected_ref: str
    inspected_head: str
    target_ref: str
    target_head: str
    branch_only_commit_count: int
    target_only_commit_count: int
    branch_only_commits: tuple[str, ...]
    exact_reachable: bool
    patch_equivalent: bool
    patch_mappings: tuple[PatchMapping, ...]
    unmapped_commits: tuple[UnmappedCommit, ...]
    integration_evidence: str
    worktree_paths: tuple[str, ...]


@dataclass(frozen=True)
class Diagnostic:
    """Fixed-code repository reconciliation diagnostic."""

    code: str
    subject: str


@dataclass(frozen=True)
class RepositoryInspection:
    """Deterministic repository-wide reconciliation report."""

    schema_version: str
    agent: str
    repository_root: str
    primary_worktree: str
    target_ref: str
    target_head: str
    canonical_branch: str
    canonical_local_head: str
    canonical_branch_only_commit_count: int
    canonical_target_only_commit_count: int
    worktree_root: str
    worktrees: tuple[WorktreeInspection, ...]
    physical_worktree_entries: tuple[PhysicalWorktreeEntry, ...]
    branches: tuple[BranchInspection, ...]
    diagnostics: tuple[Diagnostic, ...]
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable report using the published field order."""

        return asdict(self)


@dataclass(frozen=True)
class IntegrationInboxItem:
    """One published owner branch requiring Core disposition."""

    branch: str
    owner: str
    owner_confidence: str
    remote_branch: str
    branch_head: str
    branch_only_commits: tuple[str, ...]
    publication_state: str
    integration_evidence: str
    worktree_paths: tuple[str, ...]
    disposition_posture: str


@dataclass(frozen=True)
class IntegrationInbox:
    """Versioned fail-closed view of Core's pending integration work."""

    schema_version: str
    integrator: str
    target_ref: str
    target_head: str
    items: tuple[IntegrationInboxItem, ...]
    diagnostics: tuple[Diagnostic, ...]
    exit_code: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable integration-inbox report."""

        return asdict(self)


@dataclass(frozen=True)
class CloseoutEvidence:
    """Validated branch-disposition evidence for an owner record."""

    schema_version: str
    branch: str
    owner: str
    disposition: str
    terminal: bool
    target_ref: str
    target_head: str
    branch_head: str
    exact_reachable: bool
    patch_equivalent: bool
    patch_mappings: tuple[PatchMapping, ...]
    branch_only_commits: tuple[str, ...]
    remote_branch: str
    named_integrator: str
    remaining_action: str
    evidence_ref: str
    supersession: str
    evidence_sha256: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable closeout evidence record."""

        return asdict(self)


@dataclass(frozen=True)
class SyncResult:
    """Verified result of a Core-only primary-master synchronization."""

    schema_version: str
    action: str
    primary_worktree: str
    target_ref: str
    before_head: str
    target_head: str
    after_head: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable synchronization result."""

        return asdict(self)


@dataclass(frozen=True)
class _CommandResult:
    stdout: str
    stderr: str
    returncode: int


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    input_text: str | None = None,
) -> _CommandResult:
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return _CommandResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )


def _git(repo: Path, *args: str) -> _CommandResult:
    return _run(("git", "-C", str(repo), *args), cwd=repo)


def _require_git(repo: Path, *args: str, operation: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise InspectionError(
            f"{operation} failed with Git exit code {result.returncode}"
        )
    return result.stdout.strip()


def _resolve_repo_root(repo: str | Path) -> Path:
    candidate = Path(repo).resolve()
    output = _require_git(
        candidate, "rev-parse", "--show-toplevel", operation="repository discovery"
    )
    return Path(output).resolve()


def load_reconciliation_config(
    repo: str | Path,
    *,
    config_path: str | Path | None = None,
) -> ReconciliationConfig:
    """Load and validate the versioned Git reconciliation configuration.

    Args:
        repo: Repository worktree used to resolve the default configuration.
        config_path: Optional explicit configuration path.

    Returns:
        Validated reconciliation configuration.

    Raises:
        ReconciliationError: If the configuration is missing or malformed.
    """

    root = _resolve_repo_root(repo)
    path = Path(config_path).resolve() if config_path else root / DEFAULT_CONFIG_RELATIVE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconciliationError(
            f"cannot load reconciliation configuration: {path}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ReconciliationError(
            f"configuration must use {CONFIG_SCHEMA_VERSION}"
        )
    required_strings = ("canonical_remote", "canonical_branch", "worktree_root")
    for key in required_strings:
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ReconciliationError(f"configuration field {key!r} is required")
    raw_roles = payload.get("roles")
    if not isinstance(raw_roles, dict) or not raw_roles:
        raise ReconciliationError("configuration roles must be a non-empty object")
    roles: dict[str, RoleConfig] = {}
    claimed_prefixes: dict[str, str] = {}
    for raw_name, raw_role in sorted(raw_roles.items()):
        name = str(raw_name).strip().lower()
        if not isinstance(raw_role, dict):
            raise ReconciliationError(f"role {name!r} must be an object")
        display_name = raw_role.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ReconciliationError(f"role {name!r} requires display_name")
        strict = _string_tuple(raw_role.get("strict_prefixes"), f"{name}.strict_prefixes")
        legacy = _string_tuple(raw_role.get("legacy_prefixes"), f"{name}.legacy_prefixes")
        for prefix in (*strict, *legacy):
            previous = claimed_prefixes.setdefault(prefix, name)
            if previous != name:
                raise ReconciliationError(
                    f"branch prefix {prefix!r} belongs to both {previous} and {name}"
                )
        roles[name] = RoleConfig(
            name=name,
            display_name=display_name.strip(),
            strict_prefixes=strict,
            legacy_prefixes=legacy,
        )
    aliases_raw = payload.get("agent_aliases", {})
    if not isinstance(aliases_raw, dict):
        raise ReconciliationError("agent_aliases must be an object")
    aliases = {
        str(alias).strip().lower(): str(owner).strip().lower()
        for alias, owner in aliases_raw.items()
    }
    if any(owner not in roles for owner in aliases.values()):
        raise ReconciliationError("every agent alias must resolve to a configured role")
    ambiguous = _string_tuple(payload.get("ambiguous_prefixes", []), "ambiguous_prefixes")
    protected = _string_tuple(payload.get("protected_branches", []), "protected_branches")
    return ReconciliationConfig(
        schema_version=CONFIG_SCHEMA_VERSION,
        canonical_remote=payload["canonical_remote"].strip(),
        canonical_branch=payload["canonical_branch"].strip(),
        worktree_root=payload["worktree_root"].strip(),
        protected_branches=protected,
        agent_aliases=aliases,
        roles=roles,
        ambiguous_prefixes=ambiguous,
    )


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ReconciliationError(f"configuration field {field!r} must be a string list")
    return tuple(item.strip() for item in value)


def _owner_for_branch(branch: str, config: ReconciliationConfig) -> OwnerEvidence:
    if branch in config.protected_branches:
        return OwnerEvidence("core", "protected", branch)
    for name, role in sorted(config.roles.items()):
        for prefix in role.strict_prefixes:
            if branch.startswith(prefix):
                return OwnerEvidence(name, "exact", prefix)
    for name, role in sorted(config.roles.items()):
        for prefix in role.legacy_prefixes:
            if branch.startswith(prefix):
                return OwnerEvidence(name, "legacy", prefix)
    for prefix in config.ambiguous_prefixes:
        if branch.startswith(prefix):
            return OwnerEvidence("unknown", "ambiguous", prefix)
    return OwnerEvidence("unknown", "unowned", "")


def _parse_worktree_porcelain(output: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value.strip()
    if current:
        records.append(current)
    return records


def _normalized_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _operation_states(worktree: Path) -> tuple[str, ...]:
    candidates = {
        "bisect": "BISECT_LOG",
        "cherry_pick": "CHERRY_PICK_HEAD",
        "merge": "MERGE_HEAD",
        "rebase_apply": "rebase-apply",
        "rebase_merge": "rebase-merge",
        "revert": "REVERT_HEAD",
        "sequencer": "sequencer",
    }
    active: list[str] = []
    for name, git_path in candidates.items():
        result = _git(worktree, "rev-parse", "--git-path", git_path)
        if result.returncode != 0:
            raise InspectionError(
                f"Git operation inspection failed for {worktree}"
            )
        candidate = Path(result.stdout.strip())
        if not candidate.is_absolute():
            candidate = worktree / candidate
        if candidate.exists():
            active.append(name)
    return tuple(sorted(active))


def _inspect_worktrees(
    repo: Path,
    config: ReconciliationConfig,
) -> tuple[Path, tuple[WorktreeInspection, ...], tuple[PhysicalWorktreeEntry, ...]]:
    common_raw = _require_git(
        repo, "rev-parse", "--git-common-dir", operation="common Git directory discovery"
    )
    common = Path(common_raw)
    if not common.is_absolute():
        common = repo / common
    common = common.resolve()
    primary = common.parent if common.name == ".git" else repo
    raw = _require_git(
        repo, "worktree", "list", "--porcelain", operation="worktree enumeration"
    )
    records = _parse_worktree_porcelain(raw)
    configured_root = (primary / config.worktree_root).resolve()
    registered_paths: set[str] = set()
    inspected: list[WorktreeInspection] = []
    for record in records:
        if "worktree" not in record:
            raise InspectionError("worktree list returned a record without a path")
        path = Path(record["worktree"]).resolve()
        registered_paths.add(_normalized_path(path))
        is_primary = _normalized_path(path) == _normalized_path(primary)
        if is_primary:
            location_state = "primary"
        else:
            try:
                path.relative_to(configured_root)
                location_state = "configured_root"
            except ValueError:
                location_state = "outside_configured_root"
        if not path.exists():
            inspected.append(
                WorktreeInspection(
                    path=str(path),
                    head=record.get("HEAD", ""),
                    branch=_short_branch(record.get("branch", "")),
                    is_primary=is_primary,
                    status="inspection_failed",
                    clean=None,
                    operations=(),
                    location_state=location_state,
                )
            )
            continue
        status_result = _git(
            path,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--ignore-submodules=all",
        )
        if status_result.returncode != 0:
            status = "inspection_failed"
            clean: bool | None = None
            operations: tuple[str, ...] = ()
        else:
            clean = not bool(status_result.stdout)
            status = "clean" if clean else "dirty"
            operations = _operation_states(path)
        inspected.append(
            WorktreeInspection(
                path=str(path),
                head=record.get("HEAD", ""),
                branch=_short_branch(record.get("branch", "")),
                is_primary=is_primary,
                status=status,
                clean=clean,
                operations=operations,
                location_state=location_state,
            )
        )
    physical: list[PhysicalWorktreeEntry] = []
    if configured_root.exists():
        try:
            children = sorted(
                (item for item in configured_root.iterdir() if item.is_dir()),
                key=lambda item: item.name.casefold(),
            )
        except OSError as exc:
            raise InspectionError(
                f"physical worktree enumeration failed for {configured_root}"
            ) from exc
        for child in children:
            registered = _normalized_path(child) in registered_paths
            if registered:
                kind = "registered_worktree"
            elif (child / ".git").is_dir():
                kind = "standalone_clone"
            elif (child / ".git").is_file():
                kind = "unregistered_worktree_metadata"
            else:
                kind = "unregistered_directory"
            physical.append(
                PhysicalWorktreeEntry(
                    path=str(child.resolve()), kind=kind, registered=registered
                )
            )
    return (
        primary,
        tuple(sorted(inspected, key=lambda item: item.path.casefold())),
        tuple(physical),
    )


def _short_branch(ref: str) -> str:
    prefix = "refs/heads/"
    return ref[len(prefix) :] if ref.startswith(prefix) else ref


def _local_refs(repo: Path) -> dict[str, tuple[str, str]]:
    output = _require_git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)%00%(objectname)%00%(upstream:short)",
        "refs/heads/",
        operation="local branch enumeration",
    )
    refs: dict[str, tuple[str, str]] = {}
    for line in output.splitlines():
        parts = line.split("\x00")
        if len(parts) != 3:
            raise InspectionError("local branch enumeration returned malformed output")
        refs[parts[0]] = (parts[1], parts[2])
    return refs


def _remote_refs(repo: Path, remote: str) -> dict[str, str]:
    output = _require_git(
        repo,
        "for-each-ref",
        "--format=%(refname:short)%00%(objectname)",
        f"refs/remotes/{remote}/",
        operation="remote branch enumeration",
    )
    refs: dict[str, str] = {}
    prefix = f"{remote}/"
    for line in output.splitlines():
        parts = line.split("\x00")
        if len(parts) == 2 and parts[0] == remote:
            # Git shortens the symbolic ``refs/remotes/<remote>/HEAD`` ref to
            # the remote name itself.
            continue
        if len(parts) != 2 or not parts[0].startswith(prefix):
            raise InspectionError("remote branch enumeration returned malformed output")
        name = parts[0][len(prefix) :]
        if name == "HEAD":
            continue
        refs[name] = parts[1]
    return refs


def _rev_counts(repo: Path, left: str, right: str) -> tuple[int, int]:
    output = _require_git(
        repo,
        "rev-list",
        "--left-right",
        "--count",
        f"{left}...{right}",
        operation=f"divergence inspection for {left}",
    )
    parts = output.split()
    if len(parts) != 2:
        raise InspectionError("Git divergence output is malformed")
    return int(parts[0]), int(parts[1])


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = _git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise InspectionError("Git ancestry inspection failed")


def _branch_commits(repo: Path, branch_ref: str, target_ref: str) -> tuple[str, ...]:
    output = _require_git(
        repo,
        "rev-list",
        "--reverse",
        branch_ref,
        f"^{target_ref}",
        operation=f"branch-only commit enumeration for {branch_ref}",
    )
    return tuple(line for line in output.splitlines() if line)


def _patch_equivalent_candidates(
    repo: Path,
    target_ref: str,
    branch_ref: str,
    branch_commits: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    output = _require_git(
        repo,
        "rev-list",
        "--left-right",
        "--cherry-mark",
        "--no-merges",
        f"{target_ref}...{branch_ref}",
        operation=f"patch-equivalent candidate inspection for {branch_ref}",
    )
    source_commits = set(branch_commits)
    candidate_commits = sorted(
        line[1:]
        for line in output.splitlines()
        if line.startswith("=") and line[1:] not in source_commits
    )
    collected: dict[str, list[str]] = {}
    for commit in candidate_commits:
        patch_id, reason = _patch_id_for_commit(repo, commit)
        if reason:
            continue
        collected.setdefault(patch_id, []).append(commit)
    return {
        patch_id: tuple(sorted(commits))
        for patch_id, commits in sorted(collected.items())
    }


def _patch_id_for_commit(repo: Path, commit: str) -> tuple[str, str]:
    parent_line = _require_git(
        repo, "show", "-s", "--format=%P", commit, operation="commit parent inspection"
    )
    if len(parent_line.split()) > 1:
        return "", "merge_commit"
    numstat = _require_git(
        repo,
        "show",
        "--numstat",
        "--format=",
        "--no-renames",
        commit,
        operation="commit binary-change inspection",
    )
    if any(line.startswith("-\t-\t") for line in numstat.splitlines()):
        return "", "binary_change"
    show_result = _git(
        repo,
        "show",
        "--no-ext-diff",
        "--no-textconv",
        "--pretty=format:commit %H",
        commit,
    )
    if show_result.returncode != 0:
        raise InspectionError("source patch-id content inspection failed")
    patch_result = _run(
        ("git", "patch-id", "--stable"), cwd=repo, input_text=show_result.stdout
    )
    if patch_result.returncode != 0:
        raise InspectionError("stable source patch-id calculation failed")
    lines = [line for line in patch_result.stdout.splitlines() if line.strip()]
    if not lines:
        return "", "empty_commit"
    if len(lines) != 1 or len(lines[0].split()) != 2:
        raise InspectionError("stable source patch-id output is malformed")
    return lines[0].split()[0], ""


def _publication_state(
    repo: Path,
    local_head: str,
    remote_head: str,
) -> tuple[str, bool]:
    if local_head and not remote_head:
        return "local_only_unpublished", False
    if remote_head and not local_head:
        return "remote_only", True
    if local_head == remote_head:
        return "published_equal", True
    if _is_ancestor(repo, local_head, remote_head):
        return "remote_ahead", True
    if _is_ancestor(repo, remote_head, local_head):
        return "local_unpushed", False
    return "publication_diverged", False


def _inspect_branches(
    repo: Path,
    config: ReconciliationConfig,
    target_ref: str,
    target_head: str,
    worktrees: tuple[WorktreeInspection, ...],
) -> tuple[BranchInspection, ...]:
    local = _local_refs(repo)
    remote = _remote_refs(repo, config.canonical_remote)
    branches = sorted(
        (set(local) | set(remote)) - set(config.protected_branches),
        key=str.casefold,
    )
    worktree_paths: dict[str, list[str]] = {}
    for worktree in worktrees:
        if worktree.branch:
            worktree_paths.setdefault(worktree.branch, []).append(worktree.path)
    inspected: list[BranchInspection] = []
    for branch in branches:
        local_head, upstream = local.get(branch, ("", ""))
        remote_head = remote.get(branch, "")
        owner = _owner_for_branch(branch, config)
        publication_state, published_contains_local = _publication_state(
            repo, local_head, remote_head
        )
        if remote_head and published_contains_local:
            inspected_ref = f"{config.canonical_remote}/{branch}"
            inspected_head = remote_head
        else:
            inspected_ref = branch
            inspected_head = local_head
        branch_only, target_only = _rev_counts(repo, inspected_ref, target_ref)
        branch_commits = _branch_commits(repo, inspected_ref, target_ref)
        exact = _is_ancestor(repo, inspected_head, target_head)
        mappings: list[PatchMapping] = []
        unmapped: list[UnmappedCommit] = []
        patch_equivalent = False
        if not exact and branch_commits:
            target_patch_map = _patch_equivalent_candidates(
                repo,
                target_ref,
                inspected_ref,
                branch_commits,
            )
            used_targets: set[str] = set()
            for commit in branch_commits:
                patch_id, reason = _patch_id_for_commit(repo, commit)
                if reason:
                    unmapped.append(UnmappedCommit(commit, reason))
                    continue
                candidates = target_patch_map.get(patch_id, ())
                available = tuple(
                    candidate for candidate in candidates if candidate not in used_targets
                )
                if len(available) != 1:
                    unmapped.append(
                        UnmappedCommit(
                            commit,
                            "missing_patch_match"
                            if not candidates
                            else "ambiguous_patch_match",
                            tuple(candidates),
                        )
                    )
                    continue
                target_commit = available[0]
                used_targets.add(target_commit)
                mappings.append(PatchMapping(commit, patch_id, target_commit))
            patch_equivalent = len(mappings) == len(branch_commits) and not unmapped
        if exact:
            integration_evidence = "landed_exact_evidence"
        elif patch_equivalent:
            integration_evidence = "landed_patch_equivalent_evidence"
        elif branch_commits:
            integration_evidence = "not_landed"
        else:
            integration_evidence = "indeterminate"
        inspected.append(
            BranchInspection(
                branch=branch,
                owner=owner.owner,
                owner_confidence=owner.confidence,
                owner_prefix=owner.matched_prefix,
                local_head=local_head,
                remote_head=remote_head,
                upstream=upstream,
                publication_state=publication_state,
                published_contains_local_head=published_contains_local,
                inspected_ref=inspected_ref,
                inspected_head=inspected_head,
                target_ref=target_ref,
                target_head=target_head,
                branch_only_commit_count=branch_only,
                target_only_commit_count=target_only,
                branch_only_commits=branch_commits,
                exact_reachable=exact,
                patch_equivalent=patch_equivalent,
                patch_mappings=tuple(mappings),
                unmapped_commits=tuple(unmapped),
                integration_evidence=integration_evidence,
                worktree_paths=tuple(sorted(worktree_paths.get(branch, []))),
            )
        )
    return tuple(inspected)


def _core_integration_inbox_items(
    branches: Iterable[BranchInspection],
    config: ReconciliationConfig,
) -> tuple[IntegrationInboxItem, ...]:
    """Select published known-owner branches needing Core disposition.

    A branch is an inbox item only when its configured owner is known and is
    not Core, its remote ref contains the inspected local head when one exists,
    and it has commits that lack exact or complete patch-equivalent landing
    evidence on the canonical target. Worktree presence is retained as
    evidence and never interpreted as merge readiness.
    """

    items: list[IntegrationInboxItem] = []
    for branch in branches:
        if branch.owner in {"core", "unknown"}:
            continue
        if branch.owner_confidence not in {"exact", "legacy"}:
            continue
        if not branch.remote_head or not branch.published_contains_local_head:
            continue
        if branch.integration_evidence != "not_landed":
            continue
        if not branch.branch_only_commits:
            continue
        items.append(
            IntegrationInboxItem(
                branch=branch.branch,
                owner=branch.owner,
                owner_confidence=branch.owner_confidence,
                remote_branch=f"{config.canonical_remote}/{branch.branch}",
                branch_head=branch.inspected_head,
                branch_only_commits=branch.branch_only_commits,
                publication_state=branch.publication_state,
                integration_evidence=branch.integration_evidence,
                worktree_paths=branch.worktree_paths,
                disposition_posture="owner_or_core_disposition_required",
            )
        )
    return tuple(items)


def inspect_repository(
    repo: str | Path = ".",
    *,
    agent: str,
    fetch: bool = True,
    target_ref: str | None = None,
    config_path: str | Path | None = None,
) -> RepositoryInspection:
    """Inspect branch, publication, worktree, and landing evidence.

    Args:
        repo: Any worktree in the repository to inspect.
        agent: Agent role requesting the report.
        fetch: Whether to fetch and prune the configured remote first.
        target_ref: Optional inspection target; defaults to the configured
            canonical target. This does not change ``sync-main`` authority.
        config_path: Optional explicit configuration path.

    Returns:
        Deterministic repository reconciliation report.

    Raises:
        InspectionError: If Git or filesystem evidence cannot be inspected.
        ReconciliationError: If configuration or agent identity is invalid.
    """

    root = _resolve_repo_root(repo)
    config = load_reconciliation_config(root, config_path=config_path)
    normalized_agent = config.normalize_agent(agent)
    if fetch:
        fetch_result = _git(root, "fetch", config.canonical_remote, "--prune")
        if fetch_result.returncode != 0:
            raise InspectionError(
                f"fetch failed with Git exit code {fetch_result.returncode}"
            )
    target = target_ref or config.target_ref
    target_head = _require_git(
        root, "rev-parse", "--verify", target, operation="target ref resolution"
    )
    primary, worktrees, physical = _inspect_worktrees(root, config)
    branches = _inspect_branches(root, config, target, target_head, worktrees)
    local_master_result = _git(
        root, "rev-parse", "--verify", config.canonical_branch
    )
    if local_master_result.returncode != 0:
        raise InspectionError("canonical local branch is missing")
    local_master = local_master_result.stdout.strip()
    master_branch_only, master_target_only = _rev_counts(
        root, config.canonical_branch, target
    )
    diagnostics: list[Diagnostic] = []
    primary_record = next(
        (worktree for worktree in worktrees if worktree.is_primary), None
    )
    if primary_record is None:
        diagnostics.append(Diagnostic("primary_worktree_missing", str(primary)))
    else:
        if primary_record.branch != config.canonical_branch:
            diagnostics.append(
                Diagnostic("primary_worktree_not_master", primary_record.branch)
            )
        if primary_record.status == "inspection_failed":
            diagnostics.append(
                Diagnostic("worktree_status_inspection_failed", primary_record.path)
            )
        elif not primary_record.clean:
            diagnostics.append(Diagnostic("primary_worktree_dirty", primary_record.path))
        for operation in primary_record.operations:
            diagnostics.append(
                Diagnostic("primary_git_operation_active", operation)
            )
    for worktree in worktrees:
        if worktree.status == "inspection_failed" and not worktree.is_primary:
            diagnostics.append(
                Diagnostic("worktree_status_inspection_failed", worktree.path)
            )
        if worktree.location_state == "outside_configured_root":
            diagnostics.append(
                Diagnostic("worktree_outside_configured_root", worktree.path)
            )
    for entry in physical:
        if not entry.registered:
            diagnostics.append(Diagnostic(entry.kind, entry.path))
    if master_branch_only:
        diagnostics.append(
            Diagnostic("canonical_master_has_local_only_commits", str(master_branch_only))
        )
    for branch in branches:
        if branch.owner == normalized_agent and branch.integration_evidence not in {
            "landed_exact_evidence",
            "landed_patch_equivalent_evidence",
        }:
            diagnostics.append(Diagnostic("owned_branch_not_landed", branch.branch))
        if normalized_agent == "core" and branch.owner == "unknown":
            diagnostics.append(Diagnostic("branch_owner_review_required", branch.branch))
    if normalized_agent == "core":
        diagnostics.extend(
            Diagnostic("core_integration_inbox_pending", item.branch)
            for item in _core_integration_inbox_items(branches, config)
        )
    severe_codes = {"worktree_status_inspection_failed", "primary_worktree_missing"}
    if any(item.code in severe_codes for item in diagnostics):
        exit_code = 3
    elif diagnostics:
        exit_code = 2
    else:
        exit_code = 0
    return RepositoryInspection(
        schema_version=REPORT_SCHEMA_VERSION,
        agent=normalized_agent,
        repository_root=str(root),
        primary_worktree=str(primary),
        target_ref=target,
        target_head=target_head,
        canonical_branch=config.canonical_branch,
        canonical_local_head=local_master,
        canonical_branch_only_commit_count=master_branch_only,
        canonical_target_only_commit_count=master_target_only,
        worktree_root=str((primary / config.worktree_root).resolve()),
        worktrees=worktrees,
        physical_worktree_entries=physical,
        branches=branches,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: (item.code, item.subject))),
        exit_code=exit_code,
    )


def build_core_integration_inbox(
    report: RepositoryInspection,
    config: ReconciliationConfig,
) -> IntegrationInbox:
    """Build Core's integration inbox from one reconciliation inspection.

    Args:
        report: Repository inspection produced for the Core agent.
        config: Versioned reconciliation configuration used by the inspection.

    Returns:
        Versioned inbox evidence. Exit code 3 preserves inspection or safety
        failure precedence; otherwise a nonempty inbox returns exit code 2.

    Raises:
        ReconciliationError: If the inspection was not produced for Core.
    """

    if report.agent != "core":
        raise ReconciliationError("the integration inbox is available only to Core")
    items = _core_integration_inbox_items(report.branches, config)
    if report.exit_code == 3:
        exit_code = 3
    elif items or report.exit_code == 2:
        exit_code = 2
    else:
        exit_code = 0
    return IntegrationInbox(
        schema_version=INBOX_SCHEMA_VERSION,
        integrator="core",
        target_ref=report.target_ref,
        target_head=report.target_head,
        items=items,
        diagnostics=report.diagnostics,
        exit_code=exit_code,
    )


def _branch_from_report(report: RepositoryInspection, branch: str) -> BranchInspection:
    match = next((item for item in report.branches if item.branch == branch), None)
    if match is None:
        raise ReconciliationError(f"branch {branch!r} is not present in the report")
    return match


def _evidence_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_closeout_evidence(
    report: RepositoryInspection,
    branch: str,
    disposition: str,
    *,
    named_integrator: str = "",
    remote_branch: str = "",
    remaining_action: str = "",
    evidence_ref: str = "",
    supersession: str = "",
) -> CloseoutEvidence:
    """Validate and build deterministic branch closeout evidence.

    Args:
        report: Current repository inspection report.
        branch: Branch receiving the declared disposition.
        disposition: ``landed``, ``awaiting_named_integrator``, or
            ``superseded``.
        named_integrator: Exact integration owner for a pending handoff.
        remote_branch: Published remote branch containing the pending commits.
        remaining_action: Concrete integration action still required.
        evidence_ref: Durable owner record or authorization reference.
        supersession: Authorized replacement or abandonment description.

    Returns:
        Validated closeout evidence with a canonical SHA-256 identity.

    Raises:
        ReconciliationError: If the disposition lacks required evidence.
    """

    if disposition not in KNOWN_DISPOSITIONS:
        raise ReconciliationError(f"unknown branch disposition {disposition!r}")
    inspected = _branch_from_report(report, branch)
    if inspected.owner == "unknown":
        raise ReconciliationError("branch ownership must be resolved before closeout")
    if inspected.owner != report.agent:
        raise ReconciliationError(
            f"branch belongs to {inspected.owner}, not the requesting {report.agent} agent"
        )
    associated_worktrees = tuple(
        item for item in report.worktrees if item.branch == branch
    )
    if any(item.status == "inspection_failed" for item in associated_worktrees):
        raise ReconciliationError("branch worktree status inspection failed")
    if any(item.clean is not True for item in associated_worktrees):
        raise ReconciliationError("branch worktree must be clean before closeout")
    if any(item.operations for item in associated_worktrees):
        raise ReconciliationError(
            "branch worktree has an active Git operation"
        )
    if disposition == "landed" and inspected.integration_evidence not in {
        "landed_exact_evidence",
        "landed_patch_equivalent_evidence",
    }:
        raise ReconciliationError(
            "landed requires exact reachability or complete patch-equivalent evidence"
        )
    if disposition == "awaiting_named_integrator":
        expected_remote = f"origin/{branch}"
        missing = [
            name
            for name, value in (
                ("named_integrator", named_integrator),
                ("remote_branch", remote_branch),
                ("remaining_action", remaining_action),
                ("evidence_ref", evidence_ref),
            )
            if not value.strip()
        ]
        if missing:
            raise ReconciliationError(
                "awaiting_named_integrator requires " + ", ".join(missing)
            )
        if named_integrator.strip().lower() != "core":
            raise ReconciliationError("Core is the required named integration owner")
        if remote_branch != expected_remote:
            raise ReconciliationError(
                f"remote_branch must be the branch's canonical remote ref {expected_remote}"
            )
        if not inspected.remote_head or not inspected.published_contains_local_head:
            raise ReconciliationError(
                "awaiting_named_integrator requires all local commits on the remote branch"
            )
        if not inspected.branch_only_commits:
            raise ReconciliationError(
                "awaiting_named_integrator requires exact branch-only commits"
            )
    if disposition == "superseded":
        if not evidence_ref.strip() or not supersession.strip():
            raise ReconciliationError(
                "superseded requires evidence_ref and supersession"
            )
    payload: dict[str, Any] = {
        "schema_version": CLOSEOUT_SCHEMA_VERSION,
        "branch": branch,
        "owner": inspected.owner,
        "disposition": disposition,
        "terminal": disposition in TERMINAL_DISPOSITIONS,
        "target_ref": report.target_ref,
        "target_head": report.target_head,
        "branch_head": inspected.inspected_head,
        "exact_reachable": inspected.exact_reachable,
        "patch_equivalent": inspected.patch_equivalent,
        "patch_mappings": [asdict(item) for item in inspected.patch_mappings],
        "branch_only_commits": list(inspected.branch_only_commits),
        "remote_branch": remote_branch,
        "named_integrator": named_integrator,
        "remaining_action": remaining_action,
        "evidence_ref": evidence_ref,
        "supersession": supersession,
    }
    digest = _evidence_hash(payload)
    return CloseoutEvidence(
        schema_version=CLOSEOUT_SCHEMA_VERSION,
        branch=branch,
        owner=inspected.owner,
        disposition=disposition,
        terminal=disposition in TERMINAL_DISPOSITIONS,
        target_ref=report.target_ref,
        target_head=report.target_head,
        branch_head=inspected.inspected_head,
        exact_reachable=inspected.exact_reachable,
        patch_equivalent=inspected.patch_equivalent,
        patch_mappings=inspected.patch_mappings,
        branch_only_commits=inspected.branch_only_commits,
        remote_branch=remote_branch,
        named_integrator=named_integrator,
        remaining_action=remaining_action,
        evidence_ref=evidence_ref,
        supersession=supersession,
        evidence_sha256=digest,
    )


def _primary_worktree_for_sync(
    root: Path, config: ReconciliationConfig
) -> tuple[Path, WorktreeInspection]:
    primary, worktrees, _ = _inspect_worktrees(root, config)
    record = next((item for item in worktrees if item.is_primary), None)
    if record is None:
        raise SafetyError("primary worktree is not registered")
    return primary, record


def _verify_sync_preconditions(
    root: Path,
    config: ReconciliationConfig,
) -> tuple[Path, str, str]:
    primary, record = _primary_worktree_for_sync(root, config)
    if record.branch != config.canonical_branch:
        raise SafetyError("primary worktree is not checked out on master")
    if record.clean is not True:
        raise SafetyError("primary master worktree is not clean")
    if record.operations:
        raise SafetyError("primary master worktree has an active Git operation")
    before = _require_git(
        primary,
        "rev-parse",
        "--verify",
        config.canonical_branch,
        operation="local master resolution",
    )
    target = _require_git(
        primary,
        "rev-parse",
        "--verify",
        config.target_ref,
        operation="canonical target resolution",
    )
    branch_only, _ = _rev_counts(primary, config.canonical_branch, config.target_ref)
    if branch_only:
        raise SafetyError("local master contains commits absent from origin/master")
    return primary, before, target


def sync_primary_master(
    repo: str | Path = ".",
    *,
    agent: str,
    config_path: str | Path | None = None,
) -> SyncResult:
    """Fast-forward a safe primary ``master`` to ``origin/master``.

    Args:
        repo: Any worktree in the repository.
        agent: Requesting agent; must resolve exactly to Core.
        config_path: Optional explicit reconciliation configuration.

    Returns:
        Verified no-op or fast-forward synchronization result.

    Raises:
        InspectionError: If required Git evidence cannot be obtained.
        SafetyError: If any Core-only synchronization precondition fails.
    """

    root = _resolve_repo_root(repo)
    config = load_reconciliation_config(root, config_path=config_path)
    if config.normalize_agent(agent) != "core":
        raise SafetyError("only Core may synchronize the primary master branch")
    fetch_result = _git(root, "fetch", config.canonical_remote, "--prune")
    if fetch_result.returncode != 0:
        raise InspectionError(
            f"fetch failed with Git exit code {fetch_result.returncode}"
        )
    primary, before, target = _verify_sync_preconditions(root, config)
    if before == target:
        return SyncResult(
            schema_version=SYNC_SCHEMA_VERSION,
            action="already_current",
            primary_worktree=str(primary),
            target_ref=config.target_ref,
            before_head=before,
            target_head=target,
            after_head=before,
        )
    # Recheck immediately before Git takes its own index/ref locks.
    primary, before_rechecked, target_rechecked = _verify_sync_preconditions(
        root, config
    )
    if before_rechecked != before or target_rechecked != target:
        raise SafetyError("master or target changed during synchronization precheck")
    merge_result = _git(primary, "merge", "--ff-only", config.target_ref)
    if merge_result.returncode != 0:
        raise SafetyError(
            f"fast-forward failed with Git exit code {merge_result.returncode}"
        )
    after = _require_git(
        primary, "rev-parse", "HEAD", operation="post-sync master verification"
    )
    if after != target:
        raise SafetyError("post-sync master does not equal the fetched target")
    _, final_record = _primary_worktree_for_sync(root, config)
    if final_record.clean is not True or final_record.operations:
        raise SafetyError("post-sync primary master is not clean")
    return SyncResult(
        schema_version=SYNC_SCHEMA_VERSION,
        action="fast_forwarded",
        primary_worktree=str(primary),
        target_ref=config.target_ref,
        before_head=before,
        target_head=target,
        after_head=after,
    )


def _report_markdown(report: RepositoryInspection) -> str:
    lines = [
        f"# Git Reconciliation Report — {report.agent}",
        "",
        f"- Target: `{report.target_ref}` at `{report.target_head}`",
        f"- Primary worktree: `{report.primary_worktree}`",
        f"- Exit code: `{report.exit_code}`",
        "",
        "| Branch | Owner | Confidence | Branch only | Target only | Evidence | Publication |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for item in report.branches:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{item.branch}`",
                    item.owner,
                    item.owner_confidence,
                    str(item.branch_only_commit_count),
                    str(item.target_only_commit_count),
                    item.integration_evidence,
                    item.publication_state,
                )
            )
            + " |"
        )
    lines.extend(("", "## Diagnostics", ""))
    if report.diagnostics:
        lines.extend(
            f"- `{item.code}`: `{item.subject}`" for item in report.diagnostics
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _inbox_markdown(inbox: IntegrationInbox) -> str:
    lines = [
        "# Core Integration Inbox",
        "",
        f"- Target: `{inbox.target_ref}` at `{inbox.target_head}`",
        f"- Pending items: `{len(inbox.items)}`",
        f"- Exit code: `{inbox.exit_code}`",
        "",
        "| Branch | Owner | Branch-only commits | Publication | Worktrees | Posture |",
        "|---|---|---:|---|---:|---|",
    ]
    for item in inbox.items:
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{item.remote_branch}`",
                    item.owner,
                    str(len(item.branch_only_commits)),
                    item.publication_state,
                    str(len(item.worktree_paths)),
                    item.disposition_posture,
                )
            )
            + " |"
        )
    if not inbox.items:
        lines.append("| None | - | 0 | - | 0 | clear |")
    lines.extend(("", "## Diagnostics", ""))
    if inbox.diagnostics:
        lines.extend(
            f"- `{item.code}`: `{item.subject}`" for item in inbox.diagnostics
        )
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _closeout_markdown(evidence: CloseoutEvidence) -> str:
    lines = [
        "# Branch Reconciliation Closeout Evidence",
        "",
        f"- Branch: `{evidence.branch}`",
        f"- Owner: `{evidence.owner}`",
        f"- Disposition: `{evidence.disposition}`",
        f"- Terminal: `{str(evidence.terminal).lower()}`",
        f"- Target: `{evidence.target_ref}` at `{evidence.target_head}`",
        f"- Branch head: `{evidence.branch_head}`",
        f"- Evidence SHA-256: `{evidence.evidence_sha256}`",
    ]
    if evidence.patch_mappings:
        lines.extend(("", "## Patch-Equivalent Replacements", ""))
        lines.extend(
            f"- `{item.source_commit}` -> `{item.target_commit}` (`{item.patch_id}`)"
            for item in evidence.patch_mappings
        )
    if evidence.disposition == "awaiting_named_integrator":
        lines.extend(
            (
                "",
                "## Pending Integration",
                "",
                f"- Named integrator: `{evidence.named_integrator}`",
                f"- Remote branch: `{evidence.remote_branch}`",
                f"- Remaining action: {evidence.remaining_action}",
                f"- Evidence ref: `{evidence.evidence_ref}`",
            )
        )
    if evidence.disposition == "superseded":
        lines.extend(
            (
                "",
                "## Supersession",
                "",
                f"- Evidence ref: `{evidence.evidence_ref}`",
                f"- Disposition: {evidence.supersession}",
            )
        )
    return "\n".join(lines) + "\n"


def _sync_markdown(result: SyncResult) -> str:
    return (
        "# Primary Master Synchronization\n\n"
        f"- Action: `{result.action}`\n"
        f"- Primary worktree: `{result.primary_worktree}`\n"
        f"- Before: `{result.before_head}`\n"
        f"- Target: `{result.target_head}`\n"
        f"- After: `{result.after_head}`\n"
    )


def _table(report: RepositoryInspection) -> str:
    headers = (
        "branch",
        "owner",
        "confidence",
        "branch-only",
        "target-only",
        "evidence",
        "publication",
    )
    rows = [
        (
            item.branch,
            item.owner,
            item.owner_confidence,
            str(item.branch_only_commit_count),
            str(item.target_only_commit_count),
            item.integration_evidence,
            item.publication_state,
        )
        for item in report.branches
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]
    rendered = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    rendered.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    rendered.append("")
    rendered.append(f"target: {report.target_ref} {report.target_head}")
    rendered.append(f"exit_code: {report.exit_code}")
    if report.diagnostics:
        rendered.append("diagnostics:")
        rendered.extend(
            f"  {item.code}: {item.subject}" for item in report.diagnostics
        )
    return "\n".join(rendered) + "\n"


def _inbox_table(inbox: IntegrationInbox) -> str:
    headers = (
        "remote-branch",
        "owner",
        "branch-only",
        "publication",
        "worktrees",
        "posture",
    )
    rows = [
        (
            item.remote_branch,
            item.owner,
            str(len(item.branch_only_commits)),
            item.publication_state,
            str(len(item.worktree_paths)),
            item.disposition_posture,
        )
        for item in inbox.items
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        if rows
        else len(headers[index])
        for index in range(len(headers))
    ]
    rendered = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    rendered.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )
    rendered.append("")
    rendered.append(f"target: {inbox.target_ref} {inbox.target_head}")
    rendered.append(f"pending_items: {len(inbox.items)}")
    rendered.append(f"exit_code: {inbox.exit_code}")
    if inbox.diagnostics:
        rendered.append("diagnostics:")
        rendered.extend(
            f"  {item.code}: {item.subject}" for item in inbox.diagnostics
        )
    return "\n".join(rendered) + "\n"


def _json_text(value: Any) -> str:
    payload = value.to_dict() if hasattr(value, "to_dict") else value
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_or_print(text: str, *, output: str, repo_root: Path) -> None:
    if not output:
        sys.stdout.write(text)
        return
    target = Path(output)
    if not target.is_absolute():
        target = repo_root / target
    target = target.resolve()
    tmp_root = (repo_root / "tmp").resolve()
    try:
        target.relative_to(tmp_root)
    except ValueError as exc:
        raise ReconciliationError("output files must be placed under repository tmp/") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent", required=True, help="Configured agent role.")
    parser.add_argument("--repo", default=".", help="Repository worktree path.")
    parser.add_argument("--config", help="Optional reconciliation config path.")
    parser.add_argument(
        "--format", choices=("table", "json", "markdown"), default="table"
    )
    parser.add_argument("--output", default="", help="Optional path under repo tmp/.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and reconcile project owner branches."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect", help="Inspect reconciliation state.")
    _common_arguments(inspect_parser)
    inspect_parser.add_argument("--target", help="Optional read-only target ref.")
    inspect_parser.add_argument("--no-fetch", action="store_true")

    inbox_parser = subparsers.add_parser(
        "inbox", help="Show Core's published non-Core integration inbox."
    )
    _common_arguments(inbox_parser)
    inbox_parser.add_argument("--target", help="Optional read-only target ref.")
    inbox_parser.add_argument("--no-fetch", action="store_true")

    closeout_parser = subparsers.add_parser(
        "closeout", help="Build validated closeout evidence."
    )
    _common_arguments(closeout_parser)
    closeout_parser.add_argument("--branch", required=True)
    closeout_parser.add_argument(
        "--disposition", choices=tuple(sorted(KNOWN_DISPOSITIONS)), required=True
    )
    closeout_parser.add_argument("--named-integrator", default="")
    closeout_parser.add_argument("--remote-branch", default="")
    closeout_parser.add_argument("--remaining-action", default="")
    closeout_parser.add_argument("--evidence-ref", default="")
    closeout_parser.add_argument("--supersession", default="")
    closeout_parser.add_argument("--no-fetch", action="store_true")

    sync_parser = subparsers.add_parser(
        "sync-main", help="Core-only clean fast-forward of primary master."
    )
    _common_arguments(sync_parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the origin reconciler command-line interface."""

    args = _parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = inspect_repository(
                args.repo,
                agent=args.agent,
                fetch=not args.no_fetch,
                target_ref=args.target,
                config_path=args.config,
            )
            if args.format == "json":
                rendered = _json_text(report)
            elif args.format == "markdown":
                rendered = _report_markdown(report)
            else:
                rendered = _table(report)
            _write_or_print(
                rendered, output=args.output, repo_root=_resolve_repo_root(args.repo)
            )
            return report.exit_code
        if args.command == "inbox":
            repo_root = _resolve_repo_root(args.repo)
            config = load_reconciliation_config(
                repo_root, config_path=args.config
            )
            report = inspect_repository(
                repo_root,
                agent=args.agent,
                fetch=not args.no_fetch,
                target_ref=args.target,
                config_path=args.config,
            )
            inbox = build_core_integration_inbox(report, config)
            if args.format == "json":
                rendered = _json_text(inbox)
            elif args.format == "markdown":
                rendered = _inbox_markdown(inbox)
            else:
                rendered = _inbox_table(inbox)
            _write_or_print(rendered, output=args.output, repo_root=repo_root)
            return inbox.exit_code
        if args.command == "closeout":
            report = inspect_repository(
                args.repo,
                agent=args.agent,
                fetch=not args.no_fetch,
                config_path=args.config,
            )
            evidence = build_closeout_evidence(
                report,
                args.branch,
                args.disposition,
                named_integrator=args.named_integrator,
                remote_branch=args.remote_branch,
                remaining_action=args.remaining_action,
                evidence_ref=args.evidence_ref,
                supersession=args.supersession,
            )
            rendered = (
                _json_text(evidence)
                if args.format == "json"
                else _closeout_markdown(evidence)
            )
            _write_or_print(
                rendered, output=args.output, repo_root=_resolve_repo_root(args.repo)
            )
            return 0 if evidence.terminal else 2
        result = sync_primary_master(
            args.repo, agent=args.agent, config_path=args.config
        )
        rendered = (
            _json_text(result)
            if args.format == "json"
            else _sync_markdown(result)
        )
        _write_or_print(
            rendered, output=args.output, repo_root=_resolve_repo_root(args.repo)
        )
        return 0
    except (InspectionError, SafetyError, ReconciliationError) as exc:
        sys.stderr.write(f"origin_reconciler: {exc}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
