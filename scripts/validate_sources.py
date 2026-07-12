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
ALLOWED_ENGINE_MODES = {"html", "json-api"}
SUPPORTED_METHODS = {"GET"}
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
GENRE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
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
    popular_results: int = 0
    genre_results: int = 0
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
    return any(
        host == item.lower().strip(".")
        or host.endswith("." + item.lower().strip("."))
        for item in allowed
    )


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

    def replace_has(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        inner_without_attributes = re.sub(r"\[[^\]]*\]", "", inner)
        if (
            not inner
            or any(token in inner_without_attributes for token in (":", "+", "~", ">"))
            or any(character.isspace() for character in inner_without_attributes)
        ):
            raise ValidationError(
                f"{context}: :has() accepts one simple descendant selector, got {inner!r}"
            )
        return ""

    without_supported_has = re.sub(r":has\(([^()]*)\)", replace_has, without_attributes)
    if ":has(" in without_supported_has or any(
        token in without_supported_has for token in (":", "+", "~", ">")
    ):
        raise ValidationError(
            f"{context}: selector uses syntax unsupported by Yomuhon: {selector!r}"
        )


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


def validate_list_selector(selector: Any, context: str) -> None:
    if not isinstance(selector, dict):
        raise ValidationError(f"{context}: selector is required")
    container = selector.get("container")
    if not isinstance(container, str) or not container:
        raise ValidationError(f"{context}.container is required")
    assert_supported_selector(container, f"{context}.container")
    for field_name in ("title", "url", "cover"):
        field = selector.get(field_name)
        if field_name in {"title", "url"} and not isinstance(field, dict):
            raise ValidationError(f"{context}.{field_name} is required")
        for css in iter_field_selectors(field):
            assert_supported_selector(css, f"{context}.{field_name}")

    html_scope = selector.get("htmlScope")
    if html_scope is not None:
        if not isinstance(html_scope, dict):
            raise ValidationError(f"{context}.htmlScope must be an object")
        patterns = [html_scope.get("afterRegex"), html_scope.get("beforeRegex")]
        patterns = [pattern for pattern in patterns if pattern is not None]
        if not patterns:
            raise ValidationError(f"{context}.htmlScope requires afterRegex or beforeRegex")
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern:
                raise ValidationError(f"{context}.htmlScope regex must be a non-empty string")
            try:
                re.compile(pattern, re.I | re.S)
            except re.error as exc:
                raise ValidationError(f"{context}.htmlScope has invalid regex: {exc}") from exc


def validate_route(route: Any, context: str) -> None:
    if not isinstance(route, dict):
        raise ValidationError(f"{context}: route is required")
    path = route.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValidationError(f"{context}.path must start with /")


def validate_api_list_operation(operation: Any, context: str) -> None:
    if not isinstance(operation, dict):
        raise ValidationError(f"{context}: API list operation is required")
    request = operation.get("request")
    if not isinstance(request, dict):
        raise ValidationError(f"{context}.request is required")
    if request.get("method") not in SUPPORTED_METHODS:
        raise ValidationError(f"{context}.request.method must be GET")
    path = request.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValidationError(f"{context}.request.path must start with /")
    if not isinstance(operation.get("itemsPath"), str) or not operation["itemsPath"]:
        raise ValidationError(f"{context}.itemsPath is required")
    if not isinstance(operation.get("idPath"), str) or not operation["idPath"]:
        raise ValidationError(f"{context}.idPath is required")
    title_paths = operation.get("titlePaths")
    if not isinstance(title_paths, list) or not title_paths or not all(isinstance(item, str) and item for item in title_paths):
        raise ValidationError(f"{context}.titlePaths must contain at least one path")


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
    discovery = test.get("discover")
    if discovery is not None:
        if not isinstance(discovery, dict):
            raise ValidationError(f"{test_path.relative_to(ROOT)}: discover must be an object")
        for key in ("minPopularResults", "minPopularCoveredResults", "minGenreResults"):
            if key in discovery and (not isinstance(discovery[key], int) or discovery[key] < 1):
                raise ValidationError(f"{test_path.relative_to(ROOT)}: discover.{key} must be >= 1")
        if "minPopularCoveredResults" in discovery and "minPopularResults" not in discovery:
            raise ValidationError(f"{test_path.relative_to(ROOT)}: discover.minPopularResults is required when checking covers")
        genre_id = discovery.get("genreID")
        if "minGenreResults" in discovery and (not isinstance(genre_id, str) or not genre_id.strip()):
            raise ValidationError(f"{test_path.relative_to(ROOT)}: discover.genreID is required")


def validate_html_contract(config: dict[str, Any], source_id: str) -> None:
    supports = config["supports"]
    routes = config["routes"]
    selectors = config["selectors"]
    for capability in ("search", "popular"):
        if supports.get(capability) and (capability not in routes or capability not in selectors):
            raise ValidationError(
                f"{source_id}: {capability} support requires routes.{capability} and selectors.{capability}"
            )
    for capability in ("details", "chapters", "pages"):
        if supports.get(capability) and capability not in selectors:
            raise ValidationError(f"{source_id}: {capability} support requires selectors.{capability}")
    if supports.get("pages") and not supports.get("chapters"):
        raise ValidationError(f"{source_id}: pages support requires chapters support")

    for route_name, route in routes.items():
        if isinstance(route, dict):
            validate_route(route, f"{source_id}.routes.{route_name}")

    for section_name, section in selectors.items():
        if not isinstance(section, dict):
            continue
        if section_name in {"search", "popular"}:
            validate_list_selector(section, f"{source_id}.selectors.{section_name}")
        container = section.get("container")
        if isinstance(container, str):
            assert_supported_selector(container, f"{source_id}.selectors.{section_name}.container")
        for field_name, field in section.items():
            if field_name in {"container", "sort", "filters", "extractors", "number", "htmlScope"}:
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
                    try:
                        re.compile(extractor.get("pattern") or "", re.I | re.S)
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


def validate_discovery_operation(operation: Any, source_id: str, context: str, mode: str) -> None:
    if not isinstance(operation, dict):
        raise ValidationError(f"{source_id}: {context} is required")
    if mode == "html":
        validate_route(operation.get("route"), f"{source_id}.{context}.route")
        validate_list_selector(operation.get("selector"), f"{source_id}.{context}.selector")
        if operation.get("api") is not None:
            raise ValidationError(f"{source_id}: {context}.api cannot be used by an html source")
    else:
        validate_api_list_operation(operation.get("api"), f"{source_id}.{context}.api")
        if operation.get("route") is not None or operation.get("selector") is not None:
            raise ValidationError(f"{source_id}: {context}.route/selector cannot be used by a json-api source")


def validate_discovery_contract(config: dict[str, Any], source_id: str) -> None:
    supports = config["supports"]
    mode = config["engineMode"]
    discover = config.get("discover") or {}

    popular = discover.get("popular")
    if popular is not None:
        validate_discovery_operation(popular, source_id, "discover.popular", mode)
    elif mode == "json-api" and supports.get("popular"):
        raise ValidationError(f"{source_id}: json-api popular support requires discover.popular.api")

    genres = discover.get("genres")
    if supports.get("genres"):
        if not isinstance(genres, dict):
            raise ValidationError(f"{source_id}: genres support requires discover.genres")
        items = genres.get("items")
        if not isinstance(items, list) or not items:
            raise ValidationError(f"{source_id}: discover.genres.items cannot be empty")
        seen_ids: set[str] = set()
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValidationError(f"{source_id}: discover.genres.items[{position}] must be an object")
            genre_id = item.get("id")
            title = item.get("title")
            value = item.get("value")
            if not isinstance(genre_id, str) or not GENRE_ID_RE.fullmatch(genre_id):
                raise ValidationError(f"{source_id}: invalid canonical genre id {genre_id!r}")
            if genre_id in seen_ids:
                raise ValidationError(f"{source_id}: duplicate genre id {genre_id!r}")
            seen_ids.add(genre_id)
            if not isinstance(title, str) or not title.strip():
                raise ValidationError(f"{source_id}: genre {genre_id!r} has no title")
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{source_id}: genre {genre_id!r} has no source value")
        validate_discovery_operation(genres.get("operation"), source_id, "discover.genres.operation", mode)
    elif genres is not None:
        raise ValidationError(f"{source_id}: discover.genres requires supports.genres = true")


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
        # Expand the double-brace form first. Replacing {key} first would
        # turn {{key}} into {value} and leak braces into the request.
        value = value.replace("{{" + key + "}}", replacement).replace("{" + key + "}", replacement)
    return value


def request_session() -> Any:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=2, connect=2, read=2, status=2, backoff_factor=0.75,
        status_forcelist=(408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}), respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def request_json(
    session: Any, config: dict[str, Any], request: dict[str, Any],
    variables: dict[str, str], arrays: dict[str, list[str]], timeout: float,
    extra: list[tuple[str, str]] | None = None,
) -> Any:
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
    headers = {
        "Accept": "application/json", "User-Agent": "YomuhonSourceValidator/3.0",
        **((config.get("network") or {}).get("headers") or {}),
    }
    response = session.get(url, params=query, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def paginate_api(
    session: Any, config: dict[str, Any], operation: dict[str, Any],
    variables: dict[str, str], arrays: dict[str, list[str]], timeout: float,
) -> list[Any]:
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
        root = request_json(
            session, config, operation["request"], variables, arrays, timeout,
            [(pagination["offsetParam"], str(offset)), (pagination["limitParam"], str(limit))],
        )
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
        validate_discovery_contract(config, source_id)
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
    headers = {"User-Agent": "YomuhonSourceValidator/3.0", "Range": "bytes=0-2047"}
    response = session.get(url, headers=headers, timeout=timeout, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith("image/") and not IMAGE_EXT_RE.search(url):
        raise ValidationError(f"Page URL is not an image: {url}")
    next(response.iter_content(chunk_size=256), b"")
    response.close()


def fetch_html(session: Any, url: str, config: dict[str, Any], timeout: float) -> str:
    host = urlparse(url).hostname or ""
    if not domain_matches(host, config["allowedDomains"]):
        raise ValidationError(f"Blocked document host: {host}")
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 YomuhonSourceValidator/3.0",
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


def html_route_url(config: dict[str, Any], route: dict[str, Any], variables: dict[str, str], page: int | None = None) -> str:
    expanded_variables = dict(variables)
    if page is not None:
        expanded_variables["page"] = str(page)
    path = expand(route["path"], expanded_variables)
    url = urljoin(config["baseURL"].rstrip("/") + "/", path.lstrip("/"))
    items = [(key, expand(str(value), expanded_variables)) for key, value in (route.get("query") or {}).items()]
    pagination = route.get("pagination") or {}
    if page is not None and pagination.get("type") == "query" and pagination.get("param"):
        items.append((pagination["param"], str(page)))
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query=urlencode(parse_qsl(parsed.query, keep_blank_values=True) + items)))


def apply_html_scope(html_text: str, selector: dict[str, Any]) -> str:
    scope = selector.get("htmlScope") or {}
    after_pattern = scope.get("afterRegex")
    if after_pattern:
        match = re.search(after_pattern, html_text, re.I | re.S)
        if match is None:
            return ""
        html_text = html_text[match.end():]
    before_pattern = scope.get("beforeRegex")
    if before_pattern:
        match = re.search(before_pattern, html_text, re.I | re.S)
        if match is not None:
            html_text = html_text[:match.start()]
    return html_text


def canonical_html_manga_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and re.fullmatch(r"c[0-9]+(?:\.[0-9]+)?", parts[-1], re.I):
        parts.pop()
    path = "/" + "/".join(parts)
    return urlunparse(parsed._replace(path=path, query="", fragment=""))


def parse_html_list(config: dict[str, Any], html_text: str, selector: dict[str, Any]) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(apply_html_scope(html_text, selector), "html.parser")
    results_by_url: dict[str, dict[str, str]] = {}
    order: list[str] = []

    for item in soup.select(selector["container"]):
        raw_url = extract_html_field(item, selector["url"], config) or item.get("href")
        if not raw_url:
            continue
        original_url = urljoin(config["baseURL"], raw_url)
        url = canonical_html_manga_url(original_url)
        title = extract_html_field(item, selector["title"], config) or item.get_text(" ", strip=True)
        if original_url != url and (not title or re.match(r"^chapter\b", title.strip(), re.I)):
            title = None
        cover = extract_html_field(item, selector.get("cover"), config)
        cover_url = urljoin(config["baseURL"], cover) if cover else None

        existing = results_by_url.get(url)
        if existing is None:
            fallback_title = urlparse(url).path.rstrip("/").split("/")[-1].rsplit(".", 1)[0].replace("-", " ").replace("_", " ").title()
            results_by_url[url] = {
                "id": url,
                "title": cleanup_text(title or fallback_title, config),
                "url": url,
                **({"cover": cover_url} if cover_url else {}),
            }
            order.append(url)
            continue

        if title and len(cleanup_text(title, config)) > len(existing.get("title", "")):
            existing["title"] = cleanup_text(title, config)
        if cover_url and not existing.get("cover"):
            existing["cover"] = cover_url

    return [results_by_url[url] for url in order]


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
        title = extract_html_field(item, selector.get("title"), config) or item.get_text(" ", strip=True)
        number_rule = selector.get("number")
        number: float | None = None
        if isinstance(number_rule, dict):
            number_source = url if number_rule.get("from") == "url" else title
            match = re.search(number_rule["regex"], number_source, re.IGNORECASE | re.DOTALL)
            if not match:
                # A declared chapter-number rule is authoritative: reject unrelated links.
                continue
            raw_number = match.group(1) if match.groups() else match.group(0)
            try:
                number = float(raw_number)
            except ValueError:
                continue
        seen.add(url)
        chapter = {"id": url, "title": cleanup_text(title, config), "url": url}
        if number is not None:
            chapter["number"] = number
        chapters.append(chapter)
    sort_mode = selector.get("sort")
    if sort_mode in ("numberAscending", "numberDescending") and chapters and all("number" in chapter for chapter in chapters):
        chapters.sort(key=lambda chapter: (chapter["number"], chapter["id"]))
        if sort_mode == "numberDescending":
            chapters.reverse()
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


def api_list(session: Any, config: dict[str, Any], operation: dict[str, Any], variables: dict[str, str], timeout: float) -> list[Any]:
    root = request_json(session, config, operation["request"], variables, {}, timeout)
    items = json_path(root, operation["itemsPath"]) or []
    return items if isinstance(items, list) else []


def validate_live_discovery_html(report: SourceReport, session: Any, config: dict[str, Any], test: dict[str, Any], timeout: float) -> None:
    discovery_test = test.get("discover") or {}
    if "minPopularResults" in discovery_test:
        operation = (config.get("discover") or {}).get("popular") or {
            "route": (config.get("routes") or {}).get("popular"),
            "selector": (config.get("selectors") or {}).get("popular"),
        }
        url = html_route_url(config, operation["route"], {}, page=(operation["route"].get("pagination") or {}).get("start", 1))
        results = parse_html_list(config, fetch_html(session, url, config, timeout), operation["selector"])
        report.popular_results = len(results)
        if len(results) < discovery_test["minPopularResults"]:
            raise ValidationError("Popular discovery returned too few results")
        minimum_covered = discovery_test.get("minPopularCoveredResults", 0)
        if sum(1 for item in results if item.get("cover")) < minimum_covered:
            raise ValidationError("Popular discovery returned too few covered results")
    if "minGenreResults" in discovery_test:
        genres = config["discover"]["genres"]
        genre_id = discovery_test["genreID"]
        item = next((item for item in genres["items"] if item["id"] == genre_id), None)
        if item is None:
            raise ValidationError(f"Genre probe {genre_id!r} is not declared")
        operation = genres["operation"]
        route = operation["route"]
        url = html_route_url(config, route, {"genre": item["value"]}, page=(route.get("pagination") or {}).get("start", 1))
        results = parse_html_list(config, fetch_html(session, url, config, timeout), operation["selector"])
        report.genre_results = len(results)
        if len(results) < discovery_test["minGenreResults"]:
            raise ValidationError("Genre discovery returned too few results")


def validate_live_discovery_api(report: SourceReport, session: Any, config: dict[str, Any], test: dict[str, Any], timeout: float) -> None:
    discovery_test = test.get("discover") or {}
    discover = config.get("discover") or {}
    if "minPopularResults" in discovery_test:
        results = api_list(session, config, discover["popular"]["api"], {}, timeout)
        report.popular_results = len(results)
        if len(results) < discovery_test["minPopularResults"]:
            raise ValidationError("Popular discovery returned too few results")
    if "minGenreResults" in discovery_test:
        genres = discover["genres"]
        genre_id = discovery_test["genreID"]
        item = next((item for item in genres["items"] if item["id"] == genre_id), None)
        if item is None:
            raise ValidationError(f"Genre probe {genre_id!r} is not declared")
        results = api_list(session, config, genres["operation"]["api"], {"genre": item["value"]}, timeout)
        report.genre_results = len(results)
        if len(results) < discovery_test["minGenreResults"]:
            raise ValidationError("Genre discovery returned too few results")


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
        validate_live_discovery_api(report, session, config, test, timeout)
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.elapsed_seconds = round(time.monotonic() - started, 3)
        session.close()
    return report


def run_html(entry: dict[str, Any], config: dict[str, Any], test: dict[str, Any], timeout: float) -> SourceReport:
    report = SourceReport(source_id=entry["id"], status="failed")
    started = time.monotonic()
    session = request_session()
    try:
        query = (test.get("probe") or {}).get("query") or test["queries"][0]
        search_route = config["routes"]["search"]
        search_url = html_route_url(config, search_route, {"query": query})
        results = parse_html_list(config, fetch_html(session, search_url, config, timeout), config["selectors"]["search"])
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
        validate_live_discovery_html(report, session, config, test, timeout)
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.elapsed_seconds = round(time.monotonic() - started, 3)
        session.close()
    return report


def validate_live(
    index: dict[str, Any], configs: dict[str, dict[str, Any]], tests: dict[str, dict[str, Any]],
    source_ids: list[str], timeout: float, report_path: Path | None,
) -> None:
    requested = set(source_ids)
    selected = [
        entry for entry in index["sources"]
        if (not requested or entry["id"] in requested)
        and entry.get("status") not in {"broken", "disabled", "deprecated"}
    ]
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
        print(
            f"{marker}: {report.source_id} | search={report.search_results} chapters={report.chapters} "
            f"pages={report.pages} popular={report.popular_results} genres={report.genre_results} "
            f"time={report.elapsed_seconds}s" + (f" | {report.error}" if report.error else "")
        )

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(), "reports": [asdict(r) for r in reports]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
