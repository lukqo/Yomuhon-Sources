#!/usr/bin/env python3
"""Create and register a new Yomuhon declarative source skeleton."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.json"
SOURCE_DIR = ROOT / "sources"
TEST_DIR = ROOT / "tests"
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def fail(message: str) -> "NoReturn":
    raise SystemExit(f"ERROR: {message}")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Missing {path.relative_to(ROOT)}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def html_config(source_id: str, name: str, language: str, base_url: str, domains: list[str]) -> dict:
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
        "allowedDomains": domains,
        "supports": {
            "search": True,
            "popular": False,
            "details": True,
            "chapters": True,
            "pages": True,
        },
        "network": {
            "headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "User-Agent": "Yomuhon/1.0",
            }
        },
        "routes": {
            "search": {
                "path": "/search",
                "query": {"q": "{{query}}"},
            }
        },
        "selectors": {
            "search": {
                "container": "a[href*='/manga/']",
                "title": {"attrs": ["title", "text"]},
                "url": {"attrs": ["href"], "required": True},
                "cover": {"selectors": ["img"], "attrs": ["data-src", "src"]},
            },
            "details": {
                "title": {
                    "selectors": ["h1", "meta[property='og:title']"],
                    "attrs": ["text", "content"],
                },
                "synopsis": {
                    "selectors": ["meta[name='description']"],
                    "attrs": ["content"],
                },
                "cover": {
                    "selectors": ["meta[property='og:image']"],
                    "attrs": ["content"],
                },
            },
            "chapters": {
                "container": "a[href*='/chapter/']",
                "title": {"attrs": ["text", "title"]},
                "url": {"attrs": ["href"], "required": True},
                "number": {
                    "from": "url",
                    "regex": r"chapter-([0-9]+(?:\.[0-9]+)?)",
                },
                "sort": "numberAscending",
            },
            "pages": {
                "extractors": [
                    {
                        "type": "css",
                        "selector": "picture img, img.page",
                        "attrs": ["data-src", "data-original", "srcset", "src"],
                    }
                ],
                "filters": {
                    "mustContain": [".jpg", ".jpeg", ".png", ".webp"],
                    "blockContains": ["logo", "avatar", "banner", "ads/", "icon", "favicon"],
                },
            },
        },
        "cleanup": {
            "decodeHTMLEntities": True,
            "normalizeWhitespace": True,
            "removeText": [],
        },
        "tests": {
            "query": "replace-me",
            "minSearchResults": 1,
            "minChapters": 1,
            "minPages": 1,
        },
    }


def api_config(source_id: str, name: str, language: str, base_url: str, domains: list[str]) -> dict:
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
        "allowedDomains": domains,
        "supports": {
            "search": True,
            "popular": False,
            "details": True,
            "chapters": True,
            "pages": True,
        },
        "network": {
            "headers": {
                "Accept": "application/json",
                "User-Agent": "Yomuhon/1.0",
            }
        },
        "routes": {},
        "selectors": {},
        "api": {
            "search": {
                "request": {
                    "method": "GET",
                    "path": "/manga",
                    "query": {"title": "{{query}}", "limit": 20},
                },
                "itemsPath": "data",
                "idPath": "id",
                "titlePaths": ["attributes.title.en"],
                "synopsisPaths": ["attributes.description.en"],
            },
            "chapters": {
                "request": {
                    "method": "GET",
                    "path": "/manga/{mangaID}/chapters",
                    "query": {},
                },
                "pagination": {
                    "offsetParam": "offset",
                    "limitParam": "limit",
                    "limit": 100,
                    "maxItems": 10000,
                    "totalPath": "total",
                },
                "itemsPath": "data",
                "idPath": "id",
                "numberPath": "chapter",
                "titlePath": "title",
                "languagePath": "language",
                "sort": "numberAscending",
            },
            "pages": {
                "request": {
                    "method": "GET",
                    "path": "/chapter/{chapterID}/pages",
                    "query": {},
                },
                "baseURLPath": "baseUrl",
                "hashPath": "chapter.hash",
                "itemsPath": "chapter.data",
                "urlTemplate": "{baseURL}/data/{hash}/{item}",
            },
        },
        "cleanup": {
            "decodeHTMLEntities": True,
            "normalizeWhitespace": True,
            "removeText": [],
        },
        "tests": {
            "query": "replace-me",
            "minSearchResults": 1,
            "minChapters": 1,
            "minPages": 1,
        },
    }


def test_config(source_id: str) -> dict:
    return {
        "sourceID": source_id,
        "queries": ["replace-me"],
        "probe": {
            "query": "replace-me",
            "expectedTitleContains": "Replace Me",
            "mangaPathContains": None,
            "chapterPathContains": None,
        },
        "expected": {
            "minSearchResults": 1,
            "minChapters": 1,
            "minPages": 1,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, dest="source_id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--engine", required=True, choices=("html", "json-api"))
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--domain", action="append", default=[], help="Additional allowed domain; repeatable")
    args = parser.parse_args()

    source_id = args.source_id.strip()
    if not SOURCE_ID_RE.fullmatch(source_id):
        fail("--id must match ^[a-z0-9][a-z0-9_-]*$")

    parsed = urlparse(args.base_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        fail("--base-url must be an absolute HTTPS URL")

    base_url = f"https://{parsed.netloc}{parsed.path.rstrip('/')}"
    domains = [parsed.hostname.lower()]
    for domain in args.domain:
        normalized = domain.lower().strip().strip(".")
        if not normalized or "/" in normalized or ":" in normalized or " " in normalized:
            fail(f"Invalid --domain value: {domain!r}")
        if normalized not in domains:
            domains.append(normalized)

    source_path = SOURCE_DIR / f"{source_id}.json"
    test_path = TEST_DIR / f"{source_id}.test.json"
    if source_path.exists() or test_path.exists():
        fail(f"Source files already exist for {source_id}")

    index = read_json(INDEX_PATH)
    entries = index.get("sources")
    if not isinstance(entries, list):
        fail("index.json has no sources array")
    if any(entry.get("id") == source_id for entry in entries if isinstance(entry, dict)):
        fail(f"index.json already contains source id {source_id}")

    config = (
        html_config(source_id, args.name.strip(), args.language.strip(), base_url, domains)
        if args.engine == "html"
        else api_config(source_id, args.name.strip(), args.language.strip(), base_url, domains)
    )
    write_json(source_path, config)
    write_json(test_path, test_config(source_id))

    kind = "declarative-html" if args.engine == "html" else "declarative-json-api"
    entries.append(
        {
            "id": source_id,
            "name": args.name.strip(),
            "version": 1,
            "language": args.language.strip(),
            "kind": kind,
            "url": f"https://raw.githubusercontent.com/lukqo/Yomuhon-Sources/main/sources/{source_id}.json",
            "enabled": True,
            "experimental": True,
            "status": "testing",
            "allowedDomains": domains,
            "notes": f"Generated {kind} source skeleton; edit and live-validate before promotion.",
        }
    )
    entries.sort(key=lambda entry: str(entry.get("id", "")))
    index["updatedAt"] = dt.date.today().isoformat()
    write_json(INDEX_PATH, index)

    print(f"Created sources/{source_id}.json")
    print(f"Created tests/{source_id}.test.json")
    print("Registered source in index.json as testing")
    print()
    print("Next steps:")
    print(f"  1. Edit sources/{source_id}.json")
    print(f"  2. Edit tests/{source_id}.test.json")
    print("  3. python3 scripts/validate_sources.py")
    print(f"  4. python3 scripts/validate_sources.py --live --source {source_id}")
    print("  5. Test search -> detail -> chapters -> reader in Yomuhon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
