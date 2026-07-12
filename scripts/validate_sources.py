#!/usr/bin/env python3
"""Static and live validation for Yomuhon declarative sources."""
from __future__ import annotations

import argparse
import datetime as dt
import html as html_module
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "index.json"
SOURCE_DIR = ROOT / "sources"
TEST_DIR = ROOT / "tests"
SCHEMA_PATH = ROOT / "schemas" / "source-schema-v1.json"
INDEX_SCHEMA_PATH = ROOT / "schemas" / "index-schema-v1.json"
ALLOWED_STATUSES = {"stable", "testing", "broken", "disabled", "deprecated"}
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
IMAGE_EXT_RE = re.compile(r"\.(?:jpe?g|png|webp)(?:$|\?)", re.I)


class ValidationError(RuntimeError):
    pass


@dataclass
class SourceReport:
    source_id: str
    status: str
    search_results: int = 0
    chapters: int = 0
    pages: int = 0
    image_url: str | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"Missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def domain_matches(host: str, allowed: Iterable[str]) -> bool:
    host = host.lower().strip(".")
    return any(host == item.lower().strip(".") or host.endswith("." + item.lower().strip(".")) for item in allowed)


ALLOWED_ENGINE_MODES = {"html", "json-api"}
SUPPORTED_METHODS = {"GET"}


def assert_https_url(value: Any, context: str) -> None:
    parsed = urlparse(value if isinstance(value, str) else "")
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValidationError(f"{context}: expected an absolute HTTPS URL")


def assert_domains(domains: Any, context: str) -> list[str]:
    if not isinstance(domains, list) or not domains:
        raise ValidationError(f"{context}: allowedDomains cannot be empty")
    output: list[str] = []
    for domain in domains:
        if not isinstance(domain, str) or not domain or "/" in domain or ":" in domain or " " in domain:
            raise ValidationError(f"{context}: invalid allowed domain {domain!r}")
        normalized = domain.lower().strip(".")
        if normalized in output:
            raise ValidationError(f"{context}: duplicate allowed domain {domain!r}")
        output.append(normalized)
    return output


def assert_supported_selector(selector: str, context: str) -> None:
    # Colons inside attribute values (for example og:title) are valid.
    without_attributes = re.sub(r"\[[^\]]*\]", "", selector)
    if ":" in without_attributes or "+" in without_attributes or "~" in without_attributes:
        raise ValidationError(f"{context}: selector uses syntax unsupported by Yomuhon: {selector!r}")


def iter_field_selectors(value: Any) -> Iterable[str]:
    if not isinstance(value, dict):
        return
    selectors = value.get("selectors")
    if isinstance(selectors, list):
        for selector in selectors:
            if isinstance(selector, str):
                yield selector
    selector = value.get("selector")
    if isinstance(selector, str):
        yield selector


def validate_test_definition(test: dict[str, Any], source_id: str, test_path: Path) -> None:
    if test.get("sourceID") != source_id:
        raise ValidationError(f"{test_path.relative_to(ROOT)}: sourceID mismatch")
    queries = test.get("queries")
    if not isinstance(queries, list) or not queries or not all(isinstance(q, str) and q.strip() for q in queries):
        raise ValidationError(f"{test_path.relative_to(ROOT)}: queries must be non-empty strings")
    expected = test.get("expected")
    if not isinstance(expected, dict):
        raise ValidationError(f"{test_path.relative_to(ROOT)}: expected is required")
    for key in ("minSearchResults", "minChapters", "minPages"):
        if not isinstance(expected.get(key), int) or expected[key] < 1:
            raise ValidationError(f"{test_path.relative_to(ROOT)}: expected.{key} must be >= 1")


def validate_html_contract(config: dict[str, Any], source_id: str) -> None:
    supports = config["supports"]
    routes = config["routes"]
    selectors = config["selectors"]
    for capability in ("search", "popular"):
        if supports.get(capability) and (capability not in routes or capability not in selectors):
            raise ValidationError(f"{source_id}: {capability} support requires routes.{capability} and selectors.{capability}")
    for capability in ("details", "chapters", "pages"):
        if supports.get(capability) and capability not in selectors:
            raise ValidationError(f"{source_id}: {capability} support requires selectors.{capability}")
    if supports.get("pages") and not supports.get("chapters"):
        raise ValidationError(f"{source_id}: pages support requires chapters support")
    for route_name, route in routes.items():
        if not isinstance(route, dict):
            continue
        path = route.get("path")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValidationError(f"{source_id}: routes.{route_name}.path must start with /")
    for section_name, section in selectors.items():
        if not isinstance(section, dict):
            continue
        container = section.get("container")
        if isinstance(container, str):
            assert_supported_selector(container, f"{source_id}.selectors.{section_name}.container")
        for field_name, field in section.items():
            if field_name in {"container", "sort", "filters", "extractors", "number"}:
                continue
            for selector in iter_field_selectors(field):
                assert_supported_selector(selector, f"{source_id}.selectors.{section_name}.{field_name}")
        extractors = section.get("extractors", [])
        if isinstance(extractors, list):
            for position, extractor in enumerate(extractors):
                if not isinstance(extractor, dict):
                    continue
                if extractor.get("type") == "css":
                    selector = extractor.get("selector")
                    if not isinstance(selector, str) or not selector:
                        raise ValidationError(f"{source_id}: CSS extractor {position} has no selector")
                    assert_supported_selector(selector, f"{source_id}.selectors.{section_name}.extractors[{position}]")
                elif extractor.get("type") == "regex":
                    pattern = extractor.get("pattern")
                    try:
                        re.compile(pattern or "", re.I | re.S)
                    except re.error as exc:
                        raise ValidationError(f"{source_id}: invalid page regex: {exc}") from exc


def validate_api_contract(config: dict[str, Any], source_id: str) -> None:
    supports = config["supports"]
    api = config.get("api") or {}
    for capability in ("search", "chapters", "pages"):
        if supports.get(capability) and capability not in api:
            raise ValidationError(f"{source_id}: api.{capability} is required")
    for operation_name, operation in api.items():
        if not isinstance(operation, dict):
            raise ValidationError(f"{source_id}: api.{operation_name} must be an object")
        request = operation.get("request")
        if not isinstance(request, dict):
            raise ValidationError(f"{source_id}: api.{operation_name}.request is required")
        if request.get("method") not in SUPPORTED_METHODS:
            raise ValidationError(f"{source_id}: api.{operation_name}.request.method must be GET")
        path = request.get("path")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValidationError(f"{source_id}: api.{operation_name}.request.path must start with /")
    pagination = (api.get("chapters") or {}).get("pagination")
    if isinstance(pagination, dict):
        if pagination.get("offsetParam") == pagination.get("limitParam"):
            raise ValidationError(f"{source_id}: pagination offsetParam and limitParam must differ")
        limit = pagination.get("limit")
        max_items = pagination.get("maxItems", 10_000)
        if isinstance(limit, int) and isinstance(max_items, int) and max_items < limit:
            raise ValidationError(f"{source_id}: pagination maxItems cannot be lower than limit")


def json_path(root: Any, path: str) -> Any:
    current = root
    clean = path.removeprefix("$.").strip("$")
    if not clean:
        return current
    for component in clean.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(component)
    return current


def expand(value: str, variables: dict[str, str]) -> str:
    for key, replacement in variables.items():
        value = value.replace("{" + key + "}", replacement).replace("{{" + key + "}}", replacement)
    return value


def request_session() -> Any:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.75,
                  status_forcelist=(408, 425, 429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "HEAD"}), respect_retry_after_header=True)
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def request_json(session: Any, config: dict[str, Any], request: dict[str, Any], variables: dict[str, str], arrays: dict[str, list[str]], timeout: float, extra: list[tuple[str, str]] | None = None) -> Any:
    url = urljoin(config["baseURL"].rstrip("/") + "/", expand(request["path"], variables).lstrip("/"))
    host = urlparse(url).hostname or ""
    if not domain_matches(host, config["allowedDomains"]):
        raise ValidationError(f"Blocked API host: {host}")
    query: list[tuple[str, str]] = list(extra or [])
    for key, raw in (request.get("query") or {}).items():
        if isinstance(raw, str) and raw == "{{languages}}":
            query.extend((key, item) for item in arrays.get("languages", []))
        elif isinstance(raw, list):
            query.extend((key, expand(str(item), variables)) for item in raw)
        elif isinstance(raw, bool):
            query.append((key, "true" if raw else "false"))
        else:
            query.append((key, expand(str(raw), variables)))
    headers = {"Accept": "application/json", "User-Agent": "YomuhonSourceValidator/2.0", **((config.get("network") or {}).get("headers") or {})}
    response = session.get(url, params=query, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def paginate_api(session: Any, config: dict[str, Any], operation: dict[str, Any], variables: dict[str, str], arrays: dict[str, list[str]], timeout: float) -> list[Any]:
    pagination = operation.get("pagination")
    if not pagination:
        root = request_json(session, config, operation["request"], variables, arrays, timeout)
        return json_path(root, operation["itemsPath"]) or []

    limit = pagination["limit"]
    max_items = min(max(pagination.get("maxItems", 10_000), 1), 100_000)
    legacy_max_pages = pagination.get("maxPages")
    seen_ids: set[str] = set()
    seen_pages: set[tuple[str, ...]] = set()
    items: list[Any] = []
    offset = 0
    page_count = 0

    while len(items) < max_items:
        if legacy_max_pages is not None and page_count >= legacy_max_pages:
            break
        root = request_json(session, config, operation["request"], variables, arrays, timeout,
                            [(pagination["offsetParam"], str(offset)), (pagination["limitParam"], str(limit))])
        page = json_path(root, operation["itemsPath"]) or []
        if not page:
            break
        page_ids = tuple(str(json_path(item, operation["idPath"]) or "") for item in page)
        if page_ids in seen_pages:
            break
        seen_pages.add(page_ids)
        new_items = 0
        for item in page:
            item_id = str(json_path(item, operation["idPath"]) or "")
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            items.append(item)
            new_items += 1
            if len(items) >= max_items:
                break
        if new_items == 0:
            break
        total_path = pagination.get("totalPath")
        total = json_path(root, total_path) if total_path else None
        if isinstance(total, (int, float)) and len(seen_ids) >= int(total):
            break
        if len(page) < limit:
            break
        next_offset = offset + limit
        if next_offset <= offset:
            break
        offset = next_offset
        page_count += 1
    return items


def validate_static() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ValidationError("Install scripts/requirements.txt before validating") from exc

    index = load_json(INDEX_PATH)
    schema = load_json(SCHEMA_PATH)
    index_schema = load_json(INDEX_SCHEMA_PATH)
    index_errors = sorted(Draft202012Validator(index_schema).iter_errors(index), key=lambda item: list(item.path))
    if index_errors:
        rendered = "; ".join(f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in index_errors[:8])
        raise ValidationError(f"index.json failed schema validation: {rendered}")
    if index.get("schemaVersion") != 1:
        raise ValidationError("index.json: schemaVersion must be 1")
    try:
        dt.date.fromisoformat(index.get("updatedAt", ""))
    except ValueError as exc:
        raise ValidationError("index.json: updatedAt must use YYYY-MM-DD") from exc

    entries = index.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("index.json: sources must be a non-empty array")

    validator = Draft202012Validator(schema)
    configs: dict[str, dict[str, Any]] = {}
    tests: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    referenced_source_files: set[str] = set()
    referenced_test_files: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValidationError("index.json: every source entry must be an object")
        source_id = entry.get("id")
        if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id) or source_id in seen:
            raise ValidationError(f"Invalid or duplicate source id: {source_id!r}")
        seen.add(source_id)
        if entry.get("status") not in ALLOWED_STATUSES:
            raise ValidationError(f"{source_id}: invalid status")
        if not isinstance(entry.get("enabled"), bool) or not isinstance(entry.get("experimental"), bool):
            raise ValidationError(f"{source_id}: enabled and experimental must be booleans")

        remote_url = entry.get("url")
        assert_https_url(remote_url, f"{source_id}.url")
        index_domains = assert_domains(entry.get("allowedDomains"), f"{source_id}.index")
        config_path = SOURCE_DIR / Path(urlparse(remote_url).path).name
        referenced_source_files.add(config_path.name)
        config = load_json(config_path)
        schema_errors = sorted(validator.iter_errors(config), key=lambda item: list(item.path))
        if schema_errors:
            rendered = "; ".join(f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in schema_errors[:8])
            raise ValidationError(f"{config_path.relative_to(ROOT)} failed schema validation: {rendered}")

        for key in ("id", "name", "version", "language"):
            if config.get(key) != entry.get(key):
                raise ValidationError(f"{source_id}: {key} differs between index and config")

        mode = config.get("engineMode")
        if mode not in ALLOWED_ENGINE_MODES:
            raise ValidationError(f"{source_id}: unsupported engineMode {mode!r}")
        expected_kind = "declarative-json-api" if mode == "json-api" else "declarative-html"
        if entry.get("kind") != expected_kind:
            raise ValidationError(f"{source_id}: kind must be {expected_kind}")
        if config.get("enabledByDefault") is not False:
            raise ValidationError(f"{source_id}: remote sources must remain disabled by default")

        assert_https_url(config.get("baseURL"), f"{source_id}.baseURL")
        config_domains = assert_domains(config.get("allowedDomains"), f"{source_id}.config")
        base_host = urlparse(config["baseURL"]).hostname or ""
        if not domain_matches(base_host, index_domains):
            raise ValidationError(f"{source_id}: baseURL host {base_host!r} is not allowed by index.json")
        for domain in config_domains:
            if not domain_matches(domain, index_domains):
                raise ValidationError(f"{source_id}: config domain {domain!r} is not allowed by index.json")

        if mode == "html":
            validate_html_contract(config, source_id)
        else:
            validate_api_contract(config, source_id)

        configs[source_id] = config
        test_path = TEST_DIR / f"{config_path.stem}.test.json"
        referenced_test_files.add(test_path.name)
        test = load_json(test_path)
        validate_test_definition(test, source_id, test_path)
        tests[source_id] = test

    local_source_files = {path.name for path in SOURCE_DIR.glob("*.json")}
    unreferenced_sources = sorted(local_source_files - referenced_source_files)
    if unreferenced_sources:
        raise ValidationError(f"Unreferenced source configs: {', '.join(unreferenced_sources)}")
    local_test_files = {path.name for path in TEST_DIR.glob("*.test.json")}
    unreferenced_tests = sorted(local_test_files - referenced_test_files)
    if unreferenced_tests:
        raise ValidationError(f"Unreferenced test configs: {', '.join(unreferenced_tests)}")

    print(f"STATIC OK: {len(configs)} source(s), {len(tests)} live test definition(s)")
    return index, configs, tests

def first_string(root: Any, paths: list[str]) -> str | None:
    for path in paths:
        value = json_path(root, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def verify_image(session: Any, url: str, config: dict[str, Any], timeout: float) -> None:
    host = urlparse(url).hostname or ""
    if not domain_matches(host, config["allowedDomains"]):
        raise ValidationError(f"Blocked image host: {host}")
    headers = {"User-Agent": "YomuhonSourceValidator/2.0", "Range": "bytes=0-2047"}
    response = session.get(url, headers=headers, timeout=timeout, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith("image/") and not IMAGE_EXT_RE.search(url):
        raise ValidationError(f"Page URL is not an image: {url}")
    next(response.iter_content(chunk_size=256), b"")
    response.close()


def run_json_api(entry: dict[str, Any], config: dict[str, Any], test: dict[str, Any], timeout: float) -> SourceReport:
    report = SourceReport(source_id=entry["id"], status="failed")
    started = time.monotonic()
    session = request_session()
    try:
        query = (test.get("probe") or {}).get("query") or test["queries"][0]
        search = config["api"]["search"]
        root = request_json(session, config, search["request"], {"query": query}, {}, timeout)
        results = json_path(root, search["itemsPath"]) or []
        report.search_results = len(results)
        if len(results) < test["expected"]["minSearchResults"]:
            raise ValidationError("Search returned too few results")
        manga = results[0]
        manga_id = str(json_path(manga, search["idPath"]) or "")
        if not manga_id or not first_string(manga, search["titlePaths"]):
            raise ValidationError("Search mapping did not produce manga id/title")
        chapters_op = config["api"]["chapters"]
        languages = ["en", "es", "es-la"]
        chapters = paginate_api(session, config, chapters_op, {"mangaID": manga_id, "languages": ",".join(languages)}, {"languages": languages}, timeout)
        report.chapters = len(chapters)
        if len(chapters) < test["expected"]["minChapters"]:
            raise ValidationError("Chapter mapping returned too few chapters")
        chapter_id = str(json_path(chapters[0], chapters_op["idPath"]) or "")
        pages_op = config["api"]["pages"]
        root = request_json(session, config, pages_op["request"], {"chapterID": chapter_id, "mangaID": manga_id}, {}, timeout)
        base = str(json_path(root, pages_op["baseURLPath"]) or "")
        hash_value = str(json_path(root, pages_op["hashPath"]) or "")
        page_items = json_path(root, pages_op["itemsPath"]) or []
        urls = [expand(pages_op["urlTemplate"], {"baseURL": base, "hash": hash_value, "item": str(item)}) for item in page_items]
        report.pages = len(urls)
        if len(urls) < test["expected"]["minPages"]:
            raise ValidationError("Page mapping returned too few pages")
        report.image_url = urls[0]
        verify_image(session, urls[0], config, timeout)
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.elapsed_seconds = round(time.monotonic() - started, 3)
        session.close()
    return report


def fetch_html(session: Any, url: str, config: dict[str, Any], timeout: float) -> str:
    host = urlparse(url).hostname or ""
    if not domain_matches(host, config["allowedDomains"]):
        raise ValidationError(f"Blocked document host: {host}")
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 YomuhonSourceValidator/2.0",
        **((config.get("network") or {}).get("headers") or {}),
    }
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def cleanup_text(value: str, config: dict[str, Any]) -> str:
    cleanup = config.get("cleanup") or {}
    if cleanup.get("decodeHTMLEntities", True):
        value = html_module.unescape(value)
    for text in cleanup.get("removeText", []):
        value = value.replace(text, "")
    if cleanup.get("normalizeWhitespace", True):
        value = re.sub(r"\s+", " ", value).strip()
    return value.strip()


def extract_html_field(scope: Any, field: dict[str, Any] | None, config: dict[str, Any]) -> str | None:
    if not field:
        return None
    selectors = field.get("selectors") or ([field["selector"]] if field.get("selector") else [])
    candidates = []
    if selectors:
        for selector in selectors:
            selected = scope.select_one(selector)
            if selected is not None:
                candidates.append(selected)
    else:
        candidates.append(scope)
    attrs = field.get("attrs") or ([field["attr"]] if field.get("attr") else ["text"])
    for candidate in candidates:
        for attr in attrs:
            if attr == "text":
                value = candidate.get_text(" ", strip=True)
            elif attr == "html":
                value = str(candidate)
            else:
                value = candidate.get(attr)
            if isinstance(value, str) and value.strip():
                if field.get("regex"):
                    match = re.search(field["regex"], value, re.I | re.S)
                    if not match:
                        continue
                    value = match.group(1)
                return cleanup_text(value, config)
    return None


def html_route_url(config: dict[str, Any], route: dict[str, Any], query: str) -> str:
    path = route["path"].replace("{{query}}", query)
    url = urljoin(config["baseURL"].rstrip("/") + "/", path.lstrip("/"))
    items = [(key, str(value).replace("{{query}}", query)) for key, value in (route.get("query") or {}).items()]
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query=urlencode(parse_qsl(parsed.query, keep_blank_values=True) + items)))


def parse_html_search(config: dict[str, Any], html_text: str) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    selector = config["selectors"]["search"]
    soup = BeautifulSoup(html_text, "html.parser")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(selector["container"]):
        raw_url = extract_html_field(item, selector["url"], config) or item.get("href")
        title = extract_html_field(item, selector["title"], config) or item.get_text(" ", strip=True)
        if not raw_url or not title:
            continue
        url = urljoin(config["baseURL"], raw_url)
        if url in seen:
            continue
        seen.add(url)
        results.append({"id": url, "title": cleanup_text(title, config), "url": url})
    return results


def parse_html_chapters(config: dict[str, Any], html_text: str, manga_url: str) -> list[dict[str, Any]]:
    from bs4 import BeautifulSoup
    selector = config["selectors"]["chapters"]
    soup = BeautifulSoup(html_text, "html.parser")
    chapters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in soup.select(selector["container"]):
        raw_url = extract_html_field(item, selector["url"], config) or item.get("href")
        if not raw_url:
            continue
        url = urljoin(manga_url, raw_url)
        if url in seen:
            continue
        seen.add(url)
        title = extract_html_field(item, selector.get("title"), config) or item.get_text(" ", strip=True)
        chapters.append({"id": url, "title": cleanup_text(title, config), "url": url})
    return chapters


def parse_html_pages(config: dict[str, Any], html_text: str, chapter_url: str) -> list[str]:
    from bs4 import BeautifulSoup
    selector = config["selectors"]["pages"]
    filters = selector.get("filters") or {}
    soup = BeautifulSoup(html_text, "html.parser")
    urls: list[str] = []
    seen: set[str] = set()
    for extractor in selector["extractors"]:
        candidates: list[str] = []
        if extractor["type"] == "css":
            for element in soup.select(extractor.get("selector", "")):
                for attr in extractor.get("attrs", ["data-src", "data-original", "srcset", "src"]):
                    raw = element.get(attr)
                    if isinstance(raw, str):
                        candidates.extend(part.strip().split(" ")[0] for part in raw.split(",") if part.strip())
        else:
            candidates.extend(match.group(1).replace("\\/", "/") for match in re.finditer(extractor.get("pattern", ""), html_text, re.I | re.S))
        for raw in candidates:
            url = urljoin(chapter_url, raw)
            lowered = url.lower()
            required = [item.lower() for item in filters.get("mustContain", [])]
            blocked = [item.lower() for item in filters.get("blockContains", [])]
            if required and not any(item in lowered for item in required):
                continue
            if any(item in lowered for item in blocked) or url in seen:
                continue
            seen.add(url)
            urls.append(url)
    return urls


def run_html(entry: dict[str, Any], config: dict[str, Any], test: dict[str, Any], timeout: float) -> SourceReport:
    report = SourceReport(source_id=entry["id"], status="failed")
    started = time.monotonic()
    session = request_session()
    try:
        query = (test.get("probe") or {}).get("query") or test["queries"][0]
        search_url = html_route_url(config, config["routes"]["search"], query)
        results = parse_html_search(config, fetch_html(session, search_url, config, timeout))
        report.search_results = len(results)
        if len(results) < test["expected"]["minSearchResults"]:
            raise ValidationError("Search returned too few results")
        candidate = results[0]
        chapters = parse_html_chapters(config, fetch_html(session, candidate["url"], config, timeout), candidate["url"])
        report.chapters = len(chapters)
        if len(chapters) < test["expected"]["minChapters"]:
            raise ValidationError("Details returned too few chapters")
        pages = parse_html_pages(config, fetch_html(session, chapters[0]["url"], config, timeout), chapters[0]["url"])
        report.pages = len(pages)
        if len(pages) < test["expected"]["minPages"]:
            raise ValidationError("Reader returned too few pages")
        report.image_url = pages[0]
        verify_image(session, pages[0], config, timeout)
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.elapsed_seconds = round(time.monotonic() - started, 3)
        session.close()
    return report


def validate_live(index: dict[str, Any], configs: dict[str, dict[str, Any]], tests: dict[str, dict[str, Any]], source_ids: list[str], timeout: float, report_path: Path | None) -> None:
    requested = set(source_ids)
    selected = [entry for entry in index["sources"] if (not requested or entry["id"] in requested) and entry.get("status") not in {"broken", "disabled", "deprecated"}]
    selected_ids = {entry["id"] for entry in selected}
    missing = requested - selected_ids
    if missing:
        raise ValidationError(f"Unknown or non-testable source id(s): {', '.join(sorted(missing))}")
    if not selected:
        raise ValidationError("No sources selected for live validation")
    reports = []
    for entry in selected:
        config = configs[entry["id"]]
        report = run_json_api(entry, config, tests[entry["id"]], timeout) if config["engineMode"] == "json-api" else run_html(entry, config, tests[entry["id"]], timeout)
        reports.append(report)
        marker = "LIVE OK" if report.status == "passed" else "LIVE FAIL"
        print(f"{marker}: {report.source_id} | search={report.search_results} chapters={report.chapters} pages={report.pages} time={report.elapsed_seconds}s" + (f" | {report.error}" if report.error else ""))
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "reports": [asdict(r) for r in reports]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [report for report in reports if report.status != "passed"]
    if failures:
        raise ValidationError(f"{len(failures)} live source validation(s) failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        index, configs, tests = validate_static()
        if args.live:
            validate_live(index, configs, tests, args.source, args.timeout, args.report)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
