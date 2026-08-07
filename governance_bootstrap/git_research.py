"""Bounded, immutable Git-repository research capture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from .common import canonical_json, sha256_file


GIT_SNAPSHOT_SCHEMA = "git_research_snapshot_v1"
SUPPORTED_MEDIA_TYPES = {
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}
DEFAULT_MAX_FILES = 500
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 50 * 1024 * 1024
_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


class GitResearchError(RuntimeError):
    """Signal that a Git research source cannot be captured safely."""


class GitDependencyUnavailable(GitResearchError):
    """Signal that the local Git executable is unavailable."""


@dataclass(frozen=True)
class GitBlob:
    """One bounded regular file read from an exact Git tree."""

    path: str
    mode: str
    oid: str
    payload: bytes


@dataclass(frozen=True)
class GitRepositorySnapshot:
    """An exact commit/tree identity plus selected immutable blobs."""

    repository_url: str
    requested_ref: str
    commit: str
    tree: str
    tree_entry_count: int
    blobs: tuple[GitBlob, ...]


class GitRepositoryAdapter(Protocol):
    """Storage-neutral acquisition port for one exact Git snapshot."""

    def snapshot(
        self,
        *,
        repository_url: str,
        requested_ref: str,
        expected_commit: str,
        include_prefixes: tuple[str, ...],
        max_files: int,
        max_file_bytes: int,
        max_total_bytes: int,
        network_authorized: bool,
    ) -> GitRepositorySnapshot:
        """Return bounded blobs from the exact expected commit."""


class GitCliRepositoryAdapter:
    """Read a public HTTPS Git source through the installed Git executable."""

    def __init__(self, temp_root: Path) -> None:
        """Bind temporary bare-repository work to an ignored project directory."""

        self._temp_root = temp_root

    def snapshot(
        self,
        *,
        repository_url: str,
        requested_ref: str,
        expected_commit: str,
        include_prefixes: tuple[str, ...],
        max_files: int,
        max_file_bytes: int,
        max_total_bytes: int,
        network_authorized: bool,
    ) -> GitRepositorySnapshot:
        """Fetch and inspect one public ref without checking out or executing code.

        Raises:
            GitDependencyUnavailable: If the local Git executable is absent.
            GitResearchError: If authorization, identity, limits, or Git output fail.
        """

        repository_url = validate_repository_url(repository_url)
        requested_ref = validate_requested_ref(requested_ref)
        expected_commit = validate_object_id(expected_commit, "expected commit")
        include_prefixes = validate_include_prefixes(include_prefixes)
        _validate_limits(max_files, max_file_bytes, max_total_bytes)
        if not network_authorized:
            raise GitResearchError("Git research capture requires explicit network authorization")
        git = shutil.which("git")
        if git is None:
            raise GitDependencyUnavailable("the local Git executable is unavailable")

        self._temp_root.mkdir(parents=True, exist_ok=True)
        bare = Path(tempfile.mkdtemp(prefix="git-research-fetch-", dir=self._temp_root))
        try:
            self._run(git, ["init", "--bare", str(bare)], "initialize temporary repository")
            self._run(
                git,
                ["-C", str(bare), "remote", "add", "source", repository_url],
                "register temporary Git source",
            )
            self._run(
                git,
                [
                    "-C",
                    str(bare),
                    "fetch",
                    "--filter=blob:none",
                    "--depth=1",
                    "--no-tags",
                    "source",
                    requested_ref,
                ],
                "fetch authorized Git ref",
            )
            resolved = self._text(
                git,
                ["-C", str(bare), "rev-parse", "--verify", "FETCH_HEAD^{commit}"],
                "resolve fetched commit",
            ).strip().lower()
            resolved = validate_object_id(resolved, "resolved commit")
            if resolved != expected_commit:
                raise GitResearchError("the fetched ref does not match the expected commit")
            tree = self._text(
                git,
                ["-C", str(bare), "show", "-s", "--format=%T", resolved],
                "resolve commit tree",
            ).strip().lower()
            tree = validate_object_id(tree, "tree")
            listing = self._bytes(
                git,
                ["-C", str(bare), "ls-tree", "-rlz", "--full-tree", resolved],
                "list commit tree",
            )
            entries = _selected_entries(
                listing,
                include_prefixes=include_prefixes,
                max_files=max_files,
                max_file_bytes=max_file_bytes,
                max_total_bytes=max_total_bytes,
            )
            blobs = []
            for mode, oid, size, path in entries:
                payload = self._bytes(
                    git,
                    ["-C", str(bare), "cat-file", "blob", oid],
                    "read selected Git blob",
                )
                if len(payload) != size:
                    raise GitResearchError("a selected Git blob size does not match its tree entry")
                if payload.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                    raise GitResearchError(
                        "a selected Git research file is a Git LFS pointer; LFS resolution is not supported"
                    )
                blobs.append(GitBlob(path=path, mode=mode, oid=oid, payload=payload))
            return GitRepositorySnapshot(
                repository_url=repository_url,
                requested_ref=requested_ref,
                commit=resolved,
                tree=tree,
                tree_entry_count=len([entry for entry in listing.split(b"\0") if entry]),
                blobs=tuple(blobs),
            )
        finally:
            shutil.rmtree(bare, ignore_errors=True)

    @staticmethod
    def _environment() -> dict[str, str]:
        environment = dict(os.environ)
        environment.update(
            {
                "GIT_ASKPASS": "",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        return environment

    @classmethod
    def _run(
        cls, git: str, arguments: list[str], operation: str
    ) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            [git, "-c", "credential.helper=", "-c", f"core.hooksPath={os.devnull}", *arguments],
            capture_output=True,
            check=False,
            env=cls._environment(),
        )
        if result.returncode != 0:
            raise GitResearchError(f"Git could not {operation}")
        return result

    @classmethod
    def _bytes(cls, git: str, arguments: list[str], operation: str) -> bytes:
        return cls._run(git, arguments, operation).stdout

    @classmethod
    def _text(cls, git: str, arguments: list[str], operation: str) -> str:
        try:
            return cls._bytes(git, arguments, operation).decode("utf-8")
        except UnicodeDecodeError as error:
            raise GitResearchError(f"Git returned non-UTF-8 output while attempting to {operation}") from error


def validate_repository_url(value: str) -> str:
    """Return a normalized public HTTPS URL without embedded credentials."""

    if not value or any(character in value for character in "\r\n\t\\"):
        raise GitResearchError("repository URL is invalid")
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path in {"", "/"}
    ):
        raise GitResearchError("repository URL must be a public credential-free HTTPS URL")
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as error:
        raise GitResearchError("repository URL has an invalid port") from error
    if port is not None:
        host = f"{host}:{port}"
    return urlunsplit(("https", host, parsed.path.rstrip("/"), "", ""))


def validate_requested_ref(value: str) -> str:
    """Require one explicit branch or tag ref without revision syntax."""

    if (
        not value.startswith(("refs/heads/", "refs/tags/"))
        or any(token in value for token in ("..", "@{", "\\", "\r", "\n", "\t"))
        or value.endswith(("/", "."))
    ):
        raise GitResearchError("requested ref must be an explicit safe branch or tag ref")
    return value


def validate_object_id(value: str, label: str) -> str:
    """Return one normalized full SHA-1 or SHA-256 Git object ID."""

    normalized = value.lower()
    if not _OBJECT_ID.fullmatch(normalized):
        raise GitResearchError(f"{label} must be a full Git object ID")
    return normalized


def validate_include_prefixes(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return unique safe repository-relative selection prefixes."""

    normalized = []
    for value in values:
        if not value or "\\" in value:
            raise GitResearchError("include prefixes must be nonempty POSIX paths")
        path = PurePosixPath(value.rstrip("/"))
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise GitResearchError("include prefixes must stay inside the repository tree")
        normalized.append(str(path))
    return tuple(dict.fromkeys(normalized))


def capture_git_repository(
    root: Path,
    adapter: GitRepositoryAdapter,
    *,
    repository_url: str,
    requested_ref: str,
    expected_commit: str,
    title: str,
    include_prefixes: tuple[str, ...] = (),
    network_authorized: bool = False,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, object]:
    """Publish one exact bounded Git snapshot into immutable research records.

    Raises:
        GitResearchError: If source identity, selected blobs, limits, or publication fail.
    """

    repository_url = validate_repository_url(repository_url)
    requested_ref = validate_requested_ref(requested_ref)
    expected_commit = validate_object_id(expected_commit, "expected commit")
    include_prefixes = validate_include_prefixes(include_prefixes)
    _validate_limits(max_files, max_file_bytes, max_total_bytes)
    if not title.strip():
        raise GitResearchError("title is required")
    if not network_authorized:
        raise GitResearchError("Git research capture requires explicit network authorization")
    snapshot = adapter.snapshot(
        repository_url=repository_url,
        requested_ref=requested_ref,
        expected_commit=expected_commit,
        include_prefixes=include_prefixes,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
        network_authorized=network_authorized,
    )
    _validate_snapshot(
        snapshot,
        repository_url,
        requested_ref,
        expected_commit,
        include_prefixes=include_prefixes,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    if not snapshot.blobs:
        raise GitResearchError("the selected Git tree contains no supported research files")

    identity = canonical_json(
        {
            "commit": expected_commit,
            "repository_url": repository_url,
            "requested_ref": requested_ref,
        }
    )
    source_id = f"git-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:12]}"
    files = [
        {
            "git_blob_oid": blob.oid,
            "media_type": SUPPORTED_MEDIA_TYPES[PurePosixPath(blob.path).suffix.lower()],
            "mode": blob.mode,
            "path": blob.path,
            "sha256": hashlib.sha256(blob.payload).hexdigest(),
            "size": len(blob.payload),
        }
        for blob in snapshot.blobs
    ]
    manifest: dict[str, object] = {
        "schema_version": GIT_SNAPSHOT_SCHEMA,
        "source_id": source_id,
        "title": title.strip(),
        "repository_url": repository_url,
        "requested_ref": requested_ref,
        "commit": snapshot.commit,
        "tree": snapshot.tree,
        "captured_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "selection": {
            "include_prefixes": list(include_prefixes),
            "max_file_bytes": max_file_bytes,
            "max_files": max_files,
            "max_total_bytes": max_total_bytes,
            "selected_files": len(files),
            "tree_entries": snapshot.tree_entry_count,
        },
        "files": files,
        "limitations": [
            "regular Markdown, plain-text, and PDF blobs only",
            "no checkout, hooks, code execution, submodules, Git LFS, release assets, issues, or pull requests",
            "source licensing and reuse rights require separate review",
        ],
    }
    destination = root / "research/records" / source_id
    if destination.exists():
        return _verify_existing(destination, manifest)

    temporary_root = root / "tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f"{source_id}-", dir=temporary_root))
    try:
        for blob in snapshot.blobs:
            target = staging / Path(*PurePosixPath(blob.path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob.payload)
        (staging / "snapshot.json").write_text(
            canonical_json(manifest) + "\n", encoding="utf-8"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
    except OSError as error:
        raise GitResearchError("the Git research snapshot could not be published") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return manifest


def _selected_entries(
    listing: bytes,
    *,
    include_prefixes: tuple[str, ...],
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> list[tuple[str, str, int, str]]:
    entries = []
    total = 0
    for raw_entry in (entry for entry in listing.split(b"\0") if entry):
        try:
            header, raw_path = raw_entry.split(b"\t", 1)
            mode, object_type, raw_oid, raw_size = header.split()
            path = raw_path.decode("utf-8")
            mode_text = mode.decode("ascii")
        except (UnicodeDecodeError, ValueError) as error:
            raise GitResearchError("Git returned a malformed tree entry") from error
        if object_type != b"blob" or mode_text not in {"100644", "100755"}:
            continue
        try:
            oid = validate_object_id(raw_oid.decode("ascii").lower(), "blob")
            size = int(raw_size)
        except (GitResearchError, UnicodeDecodeError, ValueError) as error:
            raise GitResearchError("Git returned a malformed regular-file entry") from error
        path = _safe_tree_path(path)
        if PurePosixPath(path).suffix.lower() not in SUPPORTED_MEDIA_TYPES:
            continue
        if include_prefixes and not any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in include_prefixes
        ):
            continue
        if size > max_file_bytes:
            raise GitResearchError("a selected Git research file exceeds the per-file limit")
        total += size
        if total > max_total_bytes:
            raise GitResearchError("selected Git research files exceed the total-byte limit")
        entries.append((mode_text, oid, size, path))
        if len(entries) > max_files:
            raise GitResearchError("selected Git research files exceed the file-count limit")
    return sorted(entries, key=lambda item: item[3])


def _safe_tree_path(value: str) -> str:
    if not value or "\\" in value:
        raise GitResearchError("Git tree path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise GitResearchError("Git tree path escapes the snapshot")
    reserved = {
        "aux",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "con",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
        "nul",
        "prn",
    }
    for part in path.parts:
        if (
            any(character in part for character in '<>:"|?*\0')
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].casefold() in reserved
        ):
            raise GitResearchError("Git tree path is not portable to the project filesystem")
    return str(path)


def _validate_limits(max_files: int, max_file_bytes: int, max_total_bytes: int) -> None:
    if min(max_files, max_file_bytes, max_total_bytes) <= 0:
        raise GitResearchError("Git research limits must be positive")
    if max_file_bytes > max_total_bytes:
        raise GitResearchError("the per-file limit cannot exceed the total-byte limit")


def _validate_snapshot(
    snapshot: GitRepositorySnapshot,
    repository_url: str,
    requested_ref: str,
    expected_commit: str,
    *,
    include_prefixes: tuple[str, ...],
    max_files: int,
    max_file_bytes: int,
    max_total_bytes: int,
) -> None:
    if (
        snapshot.repository_url != repository_url
        or snapshot.requested_ref != requested_ref
        or snapshot.commit != expected_commit
    ):
        raise GitResearchError("adapter snapshot identity does not match the request")
    validate_object_id(snapshot.tree, "tree")
    if snapshot.tree_entry_count < len(snapshot.blobs):
        raise GitResearchError("adapter snapshot counts are invalid")
    if len(snapshot.blobs) > max_files:
        raise GitResearchError("adapter snapshot exceeds the file-count limit")
    paths: set[str] = set()
    portable_paths: set[str] = set()
    total = 0
    for blob in snapshot.blobs:
        path = _safe_tree_path(blob.path)
        if path in paths or path.casefold() in portable_paths:
            raise GitResearchError("adapter snapshot contains duplicate paths")
        paths.add(path)
        portable_paths.add(path.casefold())
        if blob.mode not in {"100644", "100755"}:
            raise GitResearchError("adapter snapshot contains a non-regular file")
        validate_object_id(blob.oid, "blob")
        if PurePosixPath(path).suffix.lower() not in SUPPORTED_MEDIA_TYPES:
            raise GitResearchError("adapter snapshot contains an unsupported file")
        if include_prefixes and not any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in include_prefixes
        ):
            raise GitResearchError("adapter snapshot contains a file outside the requested prefixes")
        if len(blob.payload) > max_file_bytes:
            raise GitResearchError("adapter snapshot exceeds the per-file limit")
        if blob.payload.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            raise GitResearchError(
                "adapter snapshot contains a Git LFS pointer; LFS resolution is not supported"
            )
        total += len(blob.payload)
        if total > max_total_bytes:
            raise GitResearchError("adapter snapshot exceeds the total-byte limit")


def _verify_existing(destination: Path, proposed: dict[str, object]) -> dict[str, object]:
    manifest_path = destination / "snapshot.json"
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise GitResearchError("existing Git research manifest is unreadable") from error
    identity_keys = (
        "schema_version",
        "source_id",
        "title",
        "repository_url",
        "requested_ref",
        "commit",
        "tree",
        "selection",
        "files",
        "limitations",
    )
    if any(existing.get(key) != proposed.get(key) for key in identity_keys):
        raise GitResearchError("existing Git research snapshot conflicts with the request")
    try:
        for item in existing["files"]:
            source = destination / Path(*PurePosixPath(item["path"]).parts)
            if not source.is_file() or sha256_file(source) != item["sha256"]:
                raise GitResearchError(
                    "existing Git research snapshot bytes do not match its manifest"
                )
    except (KeyError, TypeError) as error:
        raise GitResearchError("existing Git research manifest is malformed") from error
    return existing
