"""Deterministic, source-preserving research organization."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import re
from pathlib import Path
from typing import Any

from .common import canonical_json, sha256_file

TEXT_SUFFIXES = {".md", ".txt"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | PDF_SUFFIXES
PDF_PACKAGE = "pypdf"
PDF_PACKAGE_VERSION = "6.14.2"
STATUSES = {"current", "candidate", "superseded", "deadend_candidate", "evidence", "source"}


class ResearchDependencyUnavailable(RuntimeError):
    """Signal that a supported research format lacks its approved parser."""


class ResearchExtractionError(RuntimeError):
    """Signal that an exact source cannot be safely or completely extracted."""


def _record_sources(root: Path) -> list[Path]:
    records = root / "research/records"
    instructions = records / "README.md"
    return sorted(
        path
        for path in records.rglob("*")
        if path.is_file()
        and path != instructions
        and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def _pdf_reader_type() -> type[Any]:
    try:
        installed_version = version(PDF_PACKAGE)
    except PackageNotFoundError as error:
        raise ResearchDependencyUnavailable(
            "PDF extraction requires the optional pypdf==6.14.2 dependency; "
            "Core must obtain user approval before running "
            "python -m pip install -e \".[pdf]\"."
        ) from error
    if installed_version != PDF_PACKAGE_VERSION:
        raise ResearchDependencyUnavailable(
            f"PDF extraction requires pypdf=={PDF_PACKAGE_VERSION}; "
            f"the installed version is {installed_version}. Core must obtain user "
            "approval before changing the environment."
        )
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ResearchDependencyUnavailable(
            "The pypdf package metadata exists, but its PdfReader import is unavailable. "
            "Core must obtain user approval before repairing the environment."
        ) from error

    return PdfReader


def _text_sections(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"(?m)^(#{1,6}\s+.+)$", text)
    result: list[dict[str, Any]] = []
    title = path.stem
    body = parts[0]
    if body.strip():
        result.append({"title": title, "text": body.strip(), "extraction_status": "extracted"})
    for index in range(1, len(parts), 2):
        title = parts[index].lstrip("#").strip()
        body = parts[index + 1].strip()
        if body:
            result.append({"title": title, "text": body, "extraction_status": "extracted"})
    return result or [{"title": title, "text": "", "extraction_status": "no_extractable_text"}]


def _pdf_sections(path: Path) -> list[dict[str, Any]]:
    reader_type = _pdf_reader_type()
    try:
        reader = reader_type(str(path))
    except Exception as error:
        raise ResearchExtractionError(
            f"PDF record {path.name} could not be opened by the approved parser."
        ) from error
    if bool(getattr(reader, "is_encrypted", False)):
        raise ResearchExtractionError(
            f"PDF record {path.name} is encrypted; the research organizer does not request or store passwords."
        )
    try:
        pages = list(reader.pages)
    except Exception as error:
        raise ResearchExtractionError(
            f"PDF record {path.name} page structure could not be read."
        ) from error
    sections: list[dict[str, Any]] = []
    for page_number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as error:
            raise ResearchExtractionError(
                f"PDF record {path.name} page {page_number} could not be extracted."
            ) from error
        sections.append(
            {
                "title": f"Page {page_number}",
                "text": text.strip(),
                "extraction_status": "extracted" if text.strip() else "no_extractable_text",
                "page_number": page_number,
            }
        )
    return sections or [
        {
            "title": "Document",
            "text": "",
            "extraction_status": "no_pages",
            "page_number": None,
        }
    ]


def _sections(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() in PDF_SUFFIXES:
        return _pdf_sections(path)
    return _text_sections(path)


def scan(root: Path) -> dict[str, Any]:
    """Report supported, unavailable, and unsupported records without mutation."""
    records = root / "research/records"
    sources = _record_sources(root)
    pdf_error: str | None = None
    if any(path.suffix.lower() in PDF_SUFFIXES for path in sources):
        try:
            _pdf_reader_type()
        except ResearchDependencyUnavailable as error:
            pdf_error = str(error)
    supported_sources = [
        path
        for path in sources
        if path.suffix.lower() not in PDF_SUFFIXES or pdf_error is None
    ]
    unavailable = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "reason": "pdf_dependency_unavailable",
            "detail": pdf_error,
        }
        for path in sources
        if path.suffix.lower() in PDF_SUFFIXES and pdf_error is not None
    ]
    unsupported = sorted(
        path.relative_to(records).as_posix()
        for path in records.rglob("*")
        if path.is_file()
        and path != records / "README.md"
        and not path.name.startswith(".")
        and path.suffix.lower() not in SUPPORTED_SUFFIXES | {".json"}
    )
    return {
        "supported": [
            {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}
            for path in supported_sources
        ],
        "unavailable": unavailable,
        "unsupported": unsupported,
    }


def build(root: Path) -> dict[str, Any]:
    """Build a reproducible map; never mutate source records or canonical documents."""
    scan_result = scan(root)
    if scan_result["unavailable"]:
        raise ResearchDependencyUnavailable(scan_result["unavailable"][0]["detail"])
    chunks: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for source in _record_sources(root):
        source_hash = sha256_file(source)
        for index, section in enumerate(_sections(source)):
            normalized = " ".join(section["text"].lower().split())
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            source_key = source.relative_to(root).as_posix()
            candidate_id = f"candidate-{hashlib.sha256((source_key + source_hash + str(index)).encode()).hexdigest()[:12]}"
            words = set(re.findall(r"[a-z0-9_]+", normalized))
            inferred = "deadend_candidate" if any(term in normalized for term in ("dead end", "superseded", "obsolete")) else "candidate"
            candidate = {
                "candidate_id": candidate_id,
                "source": source_key,
                "source_sha256": source_hash,
                "media_type": "application/pdf" if source.suffix.lower() == ".pdf" else "text/markdown" if source.suffix.lower() == ".md" else "text/plain",
                "section": section["title"],
                "section_index": index,
                "fingerprint": fingerprint,
                "status": inferred,
                "extraction_status": section["extraction_status"],
                "word_set": sorted(words),
            }
            if "page_number" in section:
                candidate["page_number"] = section["page_number"]
            chunks.append(candidate)
            if section["extraction_status"] != "extracted":
                diagnostics.append(
                    {
                        "candidate_id": candidate_id,
                        "source": source_key,
                        "status": section["extraction_status"],
                    }
                )
    for chunk in chunks:
        duplicates = []
        own = set(chunk["word_set"])
        for other in chunks:
            if other["candidate_id"] == chunk["candidate_id"]:
                continue
            other_words = set(other["word_set"])
            union = own | other_words
            similarity = len(own & other_words) / len(union) if union else 1.0
            if chunk["fingerprint"] == other["fingerprint"]:
                duplicates.append({"candidate_id": other["candidate_id"], "kind": "exact"})
            elif similarity >= 0.85:
                duplicates.append({"candidate_id": other["candidate_id"], "kind": "near", "similarity": round(similarity, 4)})
        chunk["duplicates"] = sorted(duplicates, key=lambda item: item["candidate_id"])
    for chunk in chunks:
        del chunk["word_set"]
    result = {
        "schema_version": 2,
        "candidates": sorted(chunks, key=lambda item: item["candidate_id"]),
        "diagnostics": sorted(diagnostics, key=lambda item: item["candidate_id"]),
        "unsupported": scan_result["unsupported"],
    }
    output = root / "research/derived/research_map.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def review(root: Path, candidate_id: str, status: str, reason: str) -> dict[str, str]:
    """Write a separate human review decision for a map candidate."""
    if status not in STATUSES or not reason.strip():
        raise ValueError("a permitted status and nonempty reason are required")
    map_path = root / "research/derived/research_map.json"
    candidates = json.loads(map_path.read_text(encoding="utf-8"))["candidates"]
    if candidate_id not in {item["candidate_id"] for item in candidates}:
        raise ValueError("unknown candidate")
    decision = {"candidate_id": candidate_id, "status": status, "reason": reason}
    output = root / "research/reviews" / f"{candidate_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(decision) + "\n", encoding="utf-8")
    return decision


def may_enter_canonical(root: Path, candidate_id: str) -> bool:
    """Return true only for a separately reviewed, explicitly current candidate."""
    decision = root / "research/reviews" / f"{candidate_id}.json"
    return decision.is_file() and json.loads(decision.read_text(encoding="utf-8")).get("status") == "current"
