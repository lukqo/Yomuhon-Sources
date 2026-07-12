#!/usr/bin/env python3
"""Create and register a declarative Yomuhon source skeleton."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "sources"
TEST_DIR = ROOT / "tests"
INDEX_PATH = ROOT / "index.json"
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def html_config(source_id: str, name: str, language: str, base_url: str, host: str) -> dict:
    return {
        "schemaVersion": 1,
        "id": source_id,
        "name": name,
        "version": 1,
        "language": language,
        "baseURL": base_url,
        "engineMode": "html",
        "enabledByDefault": False,
        "experimental": True,
        "allowedDomains": [host],
        "supports": {"search": True, "popular": False, "details": True, "chapters": True, "pages": True},
        "network": {"headers": {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "User-Agent": "Yomuhon/1.0"}},
        "routes": {"search": {"path": "/search", "query": {"q": "{{query}}"}}},
        "selectors": {
            "search": {
                "container": "a[href*='/manga/']",
                "title": {"attrs": ["title", "text"]},
                "url": {"attrs": ["href"], "required": True},
                "cover": {"selectors": ["img"], "attrs": ["data-src", "src"]},
            },
            "details": {
                "title": {"selectors": ["h1", "meta[property='og:title']"], "attrs": ["text", "content"]},
                "synopsis": {"selectors": ["meta[name='description']"], "attrs": ["content"]},
                "cover": {"selectors": ["meta[property='og:image']", "img"], "attrs": ["content", "data-src", "src"]},
            },
            "chapters": {
                "container": "a[href*='/chapter/']",
                "title": {"attrs": ["text", "title"]},
                "url": {"attrs": ["href"], "required": True},
                "number": {"from": "url", "regex": "chapter[-_/]([0-9]+(?:\\.[0-9]+)?)"},
                "sort": "numberAscending",
            },
            "pages": {
                "extractors": [{"type": "css", "selector": "img", "attrs": ["data-src", "src"]}],
                "filters": {"mustContain": [".jpg", ".jpeg", ".png", ".webp"], "blockContains": ["logo", "avatar", "banner", "ads/", "icon"]},
            },
        },
        "cleanup": {"decodeHTMLEntities": True, "normalizeWhitespace": True, "removeText": []},
        "tests": {"query": "example", "minSearchResults": 1, "minChapters": 1, "minPages": 1},
    }


def api_config(source_id: str, name: str, language: str, base_url: str, host: str) -> dict:
    return {
        "schemaVersion": 1,
        "id": source_id,
        "name": name,
        "version": 1,
        "language": language,
        "baseURL": base_url,
        "engineMode": "json-api",
        "enabledByDefault": False,
        "experimental": True,
        "allowedDomains": [host],
        "supports": {"search": True, "popular": False, "details": True, "chapters": True, "pages": True},
        "network": {"headers": {"Accept": "application/json", "User-Agent": "Yomuhon/1.0"}},
        "routes": {},
        "selectors": {},
        "api": {
            "search": {
                "request": {"method": "GET", "path": "/manga", "query": {"q": "{{query}}"}},
                "itemsPath": "data",
                "idPath": "id",
                "titlePaths": ["title", "attributes.title.en"],
                "synopsisPaths": ["description", "attributes.description.en"],
            },
            "chapters": {
                "request": {"method": "GET", "path": "/manga/{mangaID}/chapters", "query": {}},
                "itemsPath": "data",
                "idPath": "id",
                "numberPath": "number",
                "titlePath": "title",
                "languagePath": "language",
                "sort": "numberAscending",
            },
            "pages": {
                "request": {"method": "GET", "path": "/chapters/{chapterID}/pages", "query": {}},
                "baseURLPath": "baseUrl",
                "hashPath": "hash",
                "itemsPath": "pages",
                "urlTemplate": "{baseURL}/{item}",
            },
        },
        "cleanup": {"decodeHTMLEntities": True, "normalizeWhitespace": True, "removeText": []},
        "tests": {"query": "example", "minSearchResults": 1, "minChapters": 1, "minPages": 1},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--engine", choices=("html", "json-api"), required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    source_id = args.id.strip().lower()
    if not SOURCE_ID_RE.fullmatch(source_id):
        parser.error("--id must match ^[a-z0-9][a-z0-9_-]*$")
    base_url = args.base_url.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        parser.error("--base-url must be an absolute HTTPS URL")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if any(entry.get("id") == source_id for entry in index.get("sources", [])):
        parser.error(f"source {source_id!r} already exists")

    source_path = SOURCE_DIR / f"{source_id}.json"
    test_path = TEST_DIR / f"{source_id}.test.json"
    if source_path.exists() or test_path.exists():
        parser.error("source or test file already exists")

    config = (
        html_config(source_id, args.name.strip(), args.language.strip(), base_url, parsed.hostname)
        if args.engine == "html"
        else api_config(source_id, args.name.strip(), args.language.strip(), base_url, parsed.hostname)
    )
    test = {
        "sourceID": source_id,
        "queries": ["example"],
        "probe": {"query": "example"},
        "expected": {"minSearchResults": 1, "minChapters": 1, "minPages": 1},
    }
    entry = {
        "id": source_id,
        "name": args.name.strip(),
        "version": 1,
        "language": args.language.strip(),
        "kind": "declarative-html" if args.engine == "html" else "declarative-json-api",
        "url": f"https://raw.githubusercontent.com/lukqo/Yomuhon-Sources/main/sources/{source_id}.json",
        "enabled": True,
        "experimental": True,
        "status": "testing",
        "allowedDomains": [parsed.hostname],
        "notes": "Generated skeleton. Replace generic routes/mappings before live validation.",
    }

    dump(source_path, config)
    dump(test_path, test)
    index["sources"].append(entry)
    index["sources"].sort(key=lambda item: item["id"])
    dump(INDEX_PATH, index)
    print(f"Created {source_path.relative_to(ROOT)}")
    print(f"Created {test_path.relative_to(ROOT)}")
    print("Registered source in index.json as testing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
