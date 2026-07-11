#!/usr/bin/env python3
"""Static and live validation for the Yomuhon declarative source repository."""

from __future__ import annotations

import argparse
import datetime as dt
import html as html_module
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
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
SOURCE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
CHAPTER_TITLE_RE = re.compile(r"^(?:chapter|ch\.?)\s*[0-9]+(?:\.[0-9]+)?(?:\s|:|-|$)", re.I)
CHAPTER_PATH_RE = re.compile(r"^(?:c|ch(?:apter)?[-_ ]?)[0-9]+(?:\.[0-9]+)?$", re.I)
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
    manga_url: str | None = None
    chapter_url: str | None = None
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


def assert_supported_selector(selector: str, context: str) -> None:
    # Colons inside attribute values (for example og:title) are valid.
    without_attributes = re.sub(r"\[[^\]]*\]", "", selector)
    if ":" in without_attributes or "+" in without_attributes or "~" in without_attributes:
        raise ValidationError(f"{context}: selector uses syntax unsupported by the app engine: {selector!r}")


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


def validate_static() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ValidationError("Install scripts/requirements.txt before validating") from exc

    index = load_json(INDEX_PATH)
    schema = load_json(SCHEMA_PATH)
    index_schema = load_json(INDEX_SCHEMA_PATH)
    schema_validator = Draft202012Validator(schema)
    index_validator = Draft202012Validator(index_schema)

    index_errors = sorted(index_validator.iter_errors(index), key=lambda item: list(item.path))
    if index_errors:
        rendered = "; ".join(f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in index_errors[:8])
        raise ValidationError(f"index.json failed schema validation: {rendered}")

    if index.get("schemaVersion") != 1:
        raise ValidationError("index.json: schemaVersion must be 1")
    if index.get("minimumAppVersion") is None:
        raise ValidationError("index.json: minimumAppVersion is required")
    try:
        dt.date.fromisoformat(index.get("updatedAt", ""))
    except ValueError as exc:
        raise ValidationError("index.json: updatedAt must use YYYY-MM-DD") from exc

    entries = index.get("sources")
    if not isinstance(entries, list) or not entries:
        raise ValidationError("index.json: sources must be a non-empty array")

    entry_by_id: dict[str, dict[str, Any]] = {}
    config_by_id: dict[str, dict[str, Any]] = {}
    test_by_id: dict[str, dict[str, Any]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValidationError("index.json: every source entry must be an object")
        source_id = entry.get("id")
        if not isinstance(source_id, str) or not SOURCE_ID_RE.fullmatch(source_id):
            raise ValidationError(f"index.json: invalid source id {source_id!r}")
        if source_id in entry_by_id:
            raise ValidationError(f"index.json: duplicate source id {source_id}")
        entry_by_id[source_id] = entry

        status = str(entry.get("status", "testing")).lower()
        if status not in ALLOWED_STATUSES:
            raise ValidationError(f"{source_id}: invalid status {status!r}")
        if entry.get("kind") != "declarative-html":
            raise ValidationError(f"{source_id}: kind must be declarative-html")
        if not isinstance(entry.get("enabled"), bool):
            raise ValidationError(f"{source_id}: enabled must be boolean")
        if not isinstance(entry.get("experimental"), bool):
            raise ValidationError(f"{source_id}: experimental must be boolean")

        remote_url = entry.get("url")
        parsed_remote = urlparse(remote_url or "")
        if parsed_remote.scheme != "https" or not parsed_remote.netloc:
            raise ValidationError(f"{source_id}: config URL must be HTTPS")

        config_path = SOURCE_DIR / Path(parsed_remote.path).name
        config = load_json(config_path)
        config_by_id[source_id] = config

        errors = sorted(schema_validator.iter_errors(config), key=lambda item: list(item.path))
        if errors:
            rendered = "; ".join(f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:8])
            raise ValidationError(f"{config_path.relative_to(ROOT)} failed schema validation: {rendered}")

        for key in ("id", "name", "version", "language"):
            if config.get(key) != entry.get(key):
                raise ValidationError(f"{source_id}: {key} differs between index.json and config")

        if config.get("engineMode") not in ALLOWED_ENGINE_MODES:
            raise ValidationError(f"{source_id}: unsupported engineMode")
        if config.get("engineMode") != "html":
            raise ValidationError(f"{source_id}: the current app only accepts html remote configs")
        if config.get("enabledByDefault") is not False:
            raise ValidationError(f"{source_id}: remote sources must remain disabled by default")

        allowed_entry = entry.get("allowedDomains")
        allowed_config = config.get("allowedDomains")
        if not isinstance(allowed_entry, list) or not allowed_entry:
            raise ValidationError(f"{source_id}: index allowedDomains cannot be empty")
        if not isinstance(allowed_config, list) or not allowed_config:
            raise ValidationError(f"{source_id}: config allowedDomains cannot be empty")
        for domain in [*allowed_entry, *allowed_config]:
            if not isinstance(domain, str) or "/" in domain or ":" in domain or " " in domain:
                raise ValidationError(f"{source_id}: invalid allowed domain {domain!r}")

        base_host = urlparse(config["baseURL"]).hostname or ""
        if not domain_matches(base_host, allowed_entry):
            raise ValidationError(f"{source_id}: baseURL host is not allowed by index.json")
        for domain in allowed_config:
            if not domain_matches(domain, allowed_entry):
                raise ValidationError(f"{source_id}: config domain {domain} is not allowed by index.json")

        supports = config["supports"]
        routes = config["routes"]
        selectors = config["selectors"]
        for capability in ("search", "popular"):
            if supports.get(capability) and (capability not in routes or capability not in selectors):
                raise ValidationError(f"{source_id}: {capability} support requires a route and selector")
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
            for pos, extractor in enumerate(section.get("extractors", [])):
                if extractor.get("type") == "css":
                    selector = extractor.get("selector")
                    if not isinstance(selector, str) or not selector:
                        raise ValidationError(f"{source_id}: CSS extractor {pos} has no selector")
                    assert_supported_selector(selector, f"{source_id}.selectors.{section_name}.extractors[{pos}]")
                elif extractor.get("type") == "regex":
                    try:
                        re.compile(extractor.get("pattern", ""), re.I | re.S)
                    except re.error as exc:
                        raise ValidationError(f"{source_id}: invalid page regex: {exc}") from exc

        test_path = TEST_DIR / f"{config_path.stem}.test.json"
        test = load_json(test_path)
        test_by_id[source_id] = test
        if test.get("sourceID") != source_id:
            raise ValidationError(f"{test_path.relative_to(ROOT)}: sourceID mismatch")
        queries = test.get("queries")
        if not isinstance(queries, list) or not queries or not all(isinstance(q, str) and q.strip() for q in queries):
            raise ValidationError(f"{test_path.relative_to(ROOT)}: queries must be non-empty strings")
        expected = test.get("expected", {})
        for key in ("minSearchResults", "minChapters", "minPages"):
            if not isinstance(expected.get(key), int) or expected[key] < 1:
                raise ValidationError(f"{test_path.relative_to(ROOT)}: expected.{key} must be >= 1")

    referenced_files = {Path(urlparse(entry["url"]).path).name for entry in entries}
    local_files = {path.name for path in SOURCE_DIR.glob("*.json")}
    unreferenced = sorted(local_files - referenced_files)
    if unreferenced:
        raise ValidationError(f"Unreferenced source configs: {', '.join(unreferenced)}")

    print(f"STATIC OK: {len(entry_by_id)} source(s), {len(test_by_id)} live test definition(s)")
    return index, config_by_id, test_by_id


def normalize_text(value: str) -> str:
    value = html_module.unescape(value)
    value = re.sub(r"<script[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def cleanup_value(value: str, pipeline: list[str] | None, cleanup: dict[str, Any] | None) -> str:
    cleanup = cleanup or {}
    if cleanup.get("decodeHTMLEntities", True):
        value = html_module.unescape(value)
    for text in cleanup.get("removeText", []):
        value = value.replace(text, "")
    for step in pipeline or []:
        if step == "stripHTML":
            value = re.sub(r"<[^>]+>", " ", value)
        elif step == "decodeEntities":
            value = html_module.unescape(value)
        elif step == "normalizeWhitespace":
            value = re.sub(r"\s+", " ", value).strip()
        elif step == "trim":
            value = value.strip()
    if cleanup.get("normalizeWhitespace", True):
        value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_field(scope: Any, field: dict[str, Any] | None, cleanup: dict[str, Any] | None) -> str | None:
    if not field:
        return None
    if field.get("regex"):
        match = re.search(field["regex"], str(scope), flags=re.I | re.S)
        if match:
            return cleanup_value(match.group(1), field.get("cleanup"), cleanup)

    selectors = field.get("selectors") or ([field["selector"]] if field.get("selector") else [])
    candidates = []
    if selectors:
        for selector in selectors:
            try:
                selected = scope.select_one(selector)
            except Exception:
                selected = None
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
                return cleanup_value(value, field.get("cleanup"), cleanup)
    return None


def route_url(config: dict[str, Any], route: dict[str, Any], query: str | None, page: int = 1) -> str:
    path = route["path"]
    if query is not None:
        path = path.replace("{{query}}", query)
    path = path.replace("{page}", str(page))
    url = urljoin(config["baseURL"].rstrip("/") + "/", path.lstrip("/"))
    query_items: list[tuple[str, str]] = []
    for key, raw_value in (route.get("query") or {}).items():
        value = raw_value.replace("{{query}}", query or "").replace("{page}", str(page))
        query_items.append((key, value))
    pagination = route.get("pagination") or {}
    if pagination.get("type") == "query" and pagination.get("param") and not any(k == pagination["param"] for k, _ in query_items):
        query_items.append((pagination["param"], str(page)))
    parsed = urlparse(url)
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    return urlunparse(parsed._replace(query=urlencode(existing + query_items)))


def canonical_manga_url(url: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and CHAPTER_PATH_RE.fullmatch(parts[-1]):
        parts.pop()
    return urlunparse(parsed._replace(path="/" + "/".join(parts), query="", fragment=""))


def manga_title(raw_title: str, manga_url: str, original_url: str) -> str:
    cleaned = normalize_text(raw_title)
    lowered = cleaned.lower()
    bad = not cleaned or lowered in {"[cover]", "cover", "image", "poster", "manga"} or CHAPTER_TITLE_RE.search(cleaned)
    if bad or manga_url != original_url:
        slug = (urlparse(manga_url).path.rstrip("/").split("/")[-1] or "untitled")
        slug = re.sub(r"\.[0-9]+$", "", slug)
        return re.sub(r"[-_]+", " ", slug).strip().title()
    return cleaned


def image_candidates(raw: str) -> list[str]:
    output: list[str] = []
    for item in raw.split(","):
        first = item.strip().split(" ")[0]
        if first:
            output.append(first.replace("\\/", "/").replace("&amp;", "&"))
    return output


def is_allowed_image(url: str, filters: dict[str, Any] | None) -> bool:
    value = url.lower()
    filters = filters or {}
    required = [item.lower() for item in filters.get("mustContain", [])]
    if required and not any(item in value for item in required):
        return False
    return not any(item.lower() in value for item in filters.get("blockContains", []))


def request_session() -> Any:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.75,
        status_forcelist=(408, 425, 429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_html(session: Any, url: str, config: dict[str, Any], timeout: float) -> str:
    host = urlparse(url).hostname or ""
    if not domain_matches(host, config["allowedDomains"]):
        raise ValidationError(f"Blocked document host: {host}")
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "Mozilla/5.0 YomuhonSourceValidator/1.0",
        **((config.get("network") or {}).get("headers") or {}),
    }
    response = session.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and not response.text.lstrip().startswith("<"):
        raise ValidationError(f"Expected HTML from {url}, got {content_type or 'unknown content type'}")
    return response.text


def parse_search(config: dict[str, Any], html_text: str) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    selector = config["selectors"]["search"]
    soup = BeautifulSoup(html_text, "html.parser")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in soup.select(selector["container"]):
        raw_url = extract_field(item, selector["url"], config.get("cleanup")) or item.get("href")
        if not raw_url:
            continue
        original_url = urljoin(config["baseURL"], raw_url)
        canonical_url = canonical_manga_url(original_url)
        if canonical_url in seen:
            continue
        raw_title = extract_field(item, selector["title"], config.get("cleanup")) or item.get_text(" ", strip=True)
        title = manga_title(raw_title, canonical_url, original_url)
        if not title:
            continue
        seen.add(canonical_url)
        output.append({"title": title, "url": canonical_url})
    return output


def parse_chapters(config: dict[str, Any], html_text: str, manga_url: str) -> list[dict[str, Any]]:
    from bs4 import BeautifulSoup

    selector = config["selectors"]["chapters"]
    soup = BeautifulSoup(html_text, "html.parser")
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in soup.select(selector["container"]):
        raw_url = extract_field(item, selector["url"], config.get("cleanup")) or item.get("href")
        if not raw_url:
            continue
        url = urljoin(manga_url, raw_url)
        title = extract_field(item, selector.get("title"), config.get("cleanup")) or item.get_text(" ", strip=True)
        last = urlparse(url).path.rstrip("/").split("/")[-1]
        if not (CHAPTER_PATH_RE.fullmatch(last) or "/chapters/" in url or "/chapter/" in url or CHAPTER_TITLE_RE.search(title)):
            continue
        if url in seen:
            continue
        seen.add(url)
        number = 0.0
        rule = selector.get("number")
        if rule:
            source = url if rule.get("from") == "url" else title
            match = re.search(rule.get("regex", ""), source, re.I)
            if match:
                try:
                    number = float(match.group(1))
                except ValueError:
                    pass
        output.append({"title": normalize_text(title), "url": url, "number": number})
    return sorted(output, key=lambda item: (item["number"], item["url"]))


def parse_pages(config: dict[str, Any], html_text: str, chapter_url: str) -> list[str]:
    from bs4 import BeautifulSoup

    selector = config["selectors"]["pages"]
    soup = BeautifulSoup(html_text, "html.parser")
    output: list[str] = []
    seen: set[str] = set()
    for extractor in selector["extractors"]:
        if extractor["type"] == "css":
            for element in soup.select(extractor["selector"]):
                for attr in extractor.get("attrs", ["data-src", "data-original", "data-lazy-src", "srcset", "src"]):
                    raw = element.get(attr)
                    if not isinstance(raw, str):
                        continue
                    for candidate in image_candidates(raw):
                        url = urljoin(chapter_url, candidate)
                        if is_allowed_image(url, selector.get("filters")) and url not in seen:
                            seen.add(url)
                            output.append(url)
        elif extractor["type"] == "regex":
            for match in re.finditer(extractor["pattern"], html_text, re.I | re.S):
                candidate = match.group(1).replace("\\/", "/").replace("&amp;", "&")
                url = urljoin(chapter_url, candidate)
                if is_allowed_image(url, selector.get("filters")) and url not in seen:
                    seen.add(url)
                    output.append(url)
    return output


def verify_image(session: Any, url: str, config: dict[str, Any], timeout: float) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 YomuhonSourceValidator/1.0",
        "Referer": config["baseURL"].rstrip("/") + "/",
        "Range": "bytes=0-2047",
        **((config.get("network") or {}).get("headers") or {}),
    }
    response = session.get(url, headers=headers, timeout=timeout, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith("image/") and not IMAGE_EXT_RE.search(url):
        raise ValidationError(f"Page URL is not an image: {url} ({content_type or 'unknown type'})")
    next(response.iter_content(chunk_size=256), b"")
    response.close()


def run_live_source(entry: dict[str, Any], config: dict[str, Any], test: dict[str, Any], timeout: float) -> SourceReport:
    source_id = entry["id"]
    report = SourceReport(source_id=source_id, status="failed")
    started = time.monotonic()
    session = request_session()
    try:
        probe = test.get("probe") or {}
        query = probe.get("query") or test["queries"][0]
        search_url = route_url(config, config["routes"]["search"], query)
        results = parse_search(config, fetch_html(session, search_url, config, timeout))
        report.search_results = len(results)
        minimum = test["expected"]["minSearchResults"]
        if len(results) < minimum:
            raise ValidationError(f"Search returned {len(results)} result(s), expected at least {minimum}")

        expected_title = str(probe.get("expectedTitleContains", "")).lower()
        candidate = next((item for item in results if expected_title and expected_title in item["title"].lower()), results[0])
        report.manga_url = candidate["url"]
        if probe.get("mangaPathContains") and probe["mangaPathContains"] not in urlparse(candidate["url"]).path:
            raise ValidationError(f"Unexpected manga URL: {candidate['url']}")

        details_html = fetch_html(session, candidate["url"], config, timeout)
        chapters = parse_chapters(config, details_html, candidate["url"])
        report.chapters = len(chapters)
        minimum = test["expected"]["minChapters"]
        if len(chapters) < minimum:
            raise ValidationError(f"Details returned {len(chapters)} chapter(s), expected at least {minimum}")

        chapter = chapters[0]
        report.chapter_url = chapter["url"]
        if probe.get("chapterPathContains") and probe["chapterPathContains"] not in urlparse(chapter["url"]).path:
            raise ValidationError(f"Unexpected chapter URL: {chapter['url']}")

        pages = parse_pages(config, fetch_html(session, chapter["url"], config, timeout), chapter["url"])
        report.pages = len(pages)
        minimum = test["expected"]["minPages"]
        if len(pages) < minimum:
            raise ValidationError(f"Reader returned {len(pages)} page(s), expected at least {minimum}")

        report.image_url = pages[0]
        verify_image(session, pages[0], config, timeout)
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001 - report every source failure uniformly
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.elapsed_seconds = round(time.monotonic() - started, 3)
        session.close()
    return report


def validate_live(
    index: dict[str, Any],
    configs: dict[str, dict[str, Any]],
    tests: dict[str, dict[str, Any]],
    source_ids: list[str],
    timeout: float,
    report_path: Path | None,
) -> None:
    selected = []
    requested = set(source_ids)
    for entry in index["sources"]:
        if requested and entry["id"] not in requested:
            continue
        if entry.get("status") in {"broken", "disabled", "deprecated"}:
            continue
        selected.append(entry)
    if requested - {entry["id"] for entry in selected}:
        missing = ", ".join(sorted(requested - {entry["id"] for entry in selected}))
        raise ValidationError(f"Unknown or non-testable source id(s): {missing}")
    if not selected:
        raise ValidationError("No sources selected for live validation")

    reports = [run_live_source(entry, configs[entry["id"]], tests[entry["id"]], timeout) for entry in selected]
    for report in reports:
        marker = "LIVE OK" if report.status == "passed" else "LIVE FAIL"
        print(
            f"{marker}: {report.source_id} | search={report.search_results} "
            f"chapters={report.chapters} pages={report.pages} time={report.elapsed_seconds}s"
            + (f" | {report.error}" if report.error else "")
        )

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "reports": [asdict(report) for report in reports],
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures = [report for report in reports if report.status != "passed"]
    if failures:
        raise ValidationError(f"{len(failures)} live source validation(s) failed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run real network smoke tests after static validation")
    parser.add_argument("--source", action="append", default=[], help="Limit live validation to a source id")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds")
    parser.add_argument("--report", type=Path, help="Write the live report as JSON")
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
