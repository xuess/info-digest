"""OPML import — convert OPML files to feeds.yaml format."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml


def parse_opml(content: str | bytes) -> list[dict[str, Any]]:
    """Parse OPML content into a list of source dicts compatible with feeds.yaml.

    Args:
        content: OPML XML content.

    Returns:
        List of source dicts with id, url, category, authority, lang, tags.
    """
    root = ET.fromstring(content)
    sources: list[dict[str, Any]] = []

    def _walk_outlines(element: ET.Element, category: str = "") -> None:
        for outline in element.findall("outline"):
            xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
            title = outline.get("title") or outline.get("text", "")
            outline_type = outline.get("type", "")

            if xml_url and outline_type.lower() in ("rss", "atom", ""):
                # Generate ID from title
                source_id = (
                    title.lower()
                    .replace(" ", "-")
                    .replace("/", "-")
                    .replace(".", "-")
                )
                # Remove consecutive dashes and trailing dashes
                while "--" in source_id:
                    source_id = source_id.replace("--", "-")
                source_id = source_id.strip("-")[:50]

                if not source_id:
                    source_id = xml_url.split("//")[-1].split("/")[0].replace(".", "-")

                sources.append({
                    "id": source_id,
                    "url": xml_url,
                    "category": category,
                    "authority": 0.5,
                    "lang": "",
                    "tags": [],
                    "enabled": False,  # Disabled by default for review
                })
            else:
                # It's a folder — recurse with folder name as category
                sub_category = title or category
                _walk_outlines(outline, sub_category)

    body = root.find("body")
    if body is not None:
        _walk_outlines(body)

    return sources


def import_opml(opml_path: str | Path, feeds_path: str | Path) -> int:
    """Import OPML file and merge into feeds.yaml.

    Returns number of new sources added.
    """
    opml_path = Path(opml_path)
    feeds_path = Path(feeds_path)

    # Parse OPML
    content = opml_path.read_text(encoding="utf-8")
    new_sources = parse_opml(content)

    # Load existing feeds
    existing: dict[str, Any] = {"sources": []}
    if feeds_path.exists():
        with open(feeds_path) as f:
            existing = yaml.safe_load(f) or {"sources": []}

    existing_ids = {s["id"] for s in existing.get("sources", [])}

    # Add new sources (skip duplicates)
    added = 0
    for src in new_sources:
        if src["id"] not in existing_ids:
            existing.setdefault("sources", []).append(src)
            existing_ids.add(src["id"])
            added += 1

    # Write back
    with open(feeds_path, "w") as f:
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return added


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import OPML into feeds.yaml")
    parser.add_argument("opml_file", help="Path to OPML file")
    parser.add_argument(
        "-o", "--output",
        default="config/feeds.yaml",
        help="Output feeds.yaml path (default: config/feeds.yaml)",
    )
    args = parser.parse_args(argv)

    added = import_opml(args.opml_file, args.output)
    print(f"Imported {added} new sources to {args.output}")
    print("Note: new sources are enabled=false. Review and enable them manually.")


if __name__ == "__main__":
    main()
