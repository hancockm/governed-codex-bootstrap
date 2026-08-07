from __future__ import annotations

import json
from pathlib import Path
import struct
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    assert payload.startswith(PNG_SIGNATURE)
    assert payload[12:16] == b"IHDR"
    return struct.unpack(">II", payload[16:24])


def test_social_asset_catalog_has_exact_sources_exports_and_alt_text() -> None:
    catalog = json.loads(
        (ROOT / "assets/social/catalog.json").read_text(encoding="utf-8")
    )
    assets = catalog["assets"]
    assert catalog["schema_version"] == "social_asset_catalog_v1"
    assert len({item["id"] for item in assets}) == len(assets) == 10
    assert sorted(item["launch_order"] for item in assets) == list(range(10))

    for asset in assets:
        source = ROOT / asset["source"]
        exported = ROOT / asset["export"]
        assert source.is_file()
        assert exported.is_file()
        assert asset["alt_text"].strip()
        assert len(asset["alt_text"]) <= 1000
        if "post_copy" in asset:
            assert asset["post_copy"].strip()
            assert len(asset["post_copy"]) <= 280
            assert asset["post_timing"].strip()

        svg = ElementTree.parse(source).getroot()
        assert int(svg.attrib["width"]) == asset["width"]
        assert int(svg.attrib["height"]) == asset["height"]
        assert _png_dimensions(exported) == (asset["width"], asset["height"])


def test_x_exports_respect_registered_upload_size_boundaries() -> None:
    catalog = json.loads(
        (ROOT / "assets/social/catalog.json").read_text(encoding="utf-8")
    )
    for asset in catalog["assets"]:
        exported = ROOT / asset["export"]
        limit = 2_000_000 if asset["id"] == "x-profile-header" else 5_000_000
        assert exported.stat().st_size <= limit
