#!/usr/bin/env python3
#llama-quantize ./granite-4.0-350m-Q4_K_M.gguf ./granite4.gguf q4_k_m
import sys
import os
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import html
from html.parser import HTMLParser
from datetime import datetime

# LiteRT-LM is only required when default.txt contains 1.
try:
    import litert_lm
except ImportError:
    litert_lm = None


# ============================================================
# SETTINGS
# ============================================================

MAX_RESULTS = 15
SEARCH_TIMEOUT = 20
PAGE_FETCH_LIMIT = 8
LINKS_PER_PAGE = 2
PAGE_CHAR_LIMIT = 5000
TOTAL_WEB_CHAR_LIMIT = 18000
MODEL_WEB_CHAR_LIMIT = 8000


# ============================================================
# MODEL TOKEN SIZE SETTINGS
# ============================================================
#
# GGUF / Ollama:
#   Controls the Ollama context size.
#
# LiteRT-LM:
#   Controls the maximum number of tokens allocated to the
#   LiteRT-LM engine/KV cache.
#
# Change these independently.
#
# Examples:
#
# GGUF_TOKEN_SIZE = 8192
# LITERT_TOKEN_SIZE = 2048
#
# or:
#
# GGUF_TOKEN_SIZE = 16384
# LITERT_TOKEN_SIZE = 8192
#
# The LiteRT-LM value cannot exceed what the particular
# .litertlm model/runtime can actually support.
# ============================================================

GGUF_TOKEN_SIZE = 8192
LITERT_TOKEN_SIZE = 4096


# ============================================================
# MODEL BACKEND SETTINGS
# ============================================================
#
# default.txt:
#   1 = LiteRT-LM
#   2 = Ollama / GGUF
#
# For mode 2, the GGUF model should be imported into Ollama.
# Set OLLAMA_MODEL below, or use the OLLAMA_MODEL environment
# variable when launching the script.
#
DEFAULT_FILE = "/data/data/com.termux/files/usr/bin/default.txt"
LITERT_MODEL_PATH = "/storage/emulated/0/gemma-4-E2B-it.litertlm"

OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_MODEL = "granite4"
OLLAMA_TIMEOUT = 300


USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0.0.0 Mobile Safari/537.36"
)


# ============================================================
# STATUS
# ============================================================

def status(message, color="yellow"):

    colors = {
        "yellow": "\033[33m",
        "green": "\033[32m",
        "red": "\033[31m",
        "cyan": "\033[36m",
        "reset": "\033[0m",
    }

    print(
        colors.get(color, "")
        + message
        + colors["reset"],
        file=sys.stderr
    )


# ============================================================
# CLEAN HTML
# ============================================================

def clean_html(text):

    if not text:
        return ""

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# DECODE DUCKDUCKGO REDIRECT URL
# ============================================================

def decode_url(url):

    if not url:
        return ""

    url = html.unescape(url)

    try:

        parsed = urllib.parse.urlparse(url)

        params = urllib.parse.parse_qs(
            parsed.query
        )

        if "uddg" in params:

            return urllib.parse.unquote(
                params["uddg"][0]
            )

    except Exception:
        pass

    return url


# ============================================================
# EXTRACT SNIPPET
# ============================================================

def extract_snippet(
    page,
    position
):

    section = page[
        position:
        position + 8000
    ]

    patterns = [

        r'class=["\'][^"\']*result__snippet[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</',

        r'class=["\'][^"\']*result-snippet[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</',

        r'class=["\'][^"\']*snippet[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            section,
            flags=re.I | re.S
        )

        if match:

            return clean_html(
                match.group(1)
            )

    return ""


# ============================================================
# PARSE STANDARD DUCKDUCKGO HTML
# ============================================================

def parse_standard_results(page):

    results = []

    patterns = [

        # href before class
        r'<a[^>]+href=["\']([^"\']+)["\'][^>]+'
        r'class=["\'][^"\']*result__a[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</a>',

        # class before href
        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+'
        r'href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',
    ]

    matches = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            page,
            flags=re.I | re.S
        )

        if matches:
            break

    for href, title_html in matches:

        title = clean_html(
            title_html
        )

        url = decode_url(
            href
        )

        if not title:
            continue

        if not url:
            continue

        if not url.startswith(
            ("http://", "https://")
        ):
            continue

        position = page.find(
            title_html
        )

        snippet = ""

        if position >= 0:

            snippet = extract_snippet(
                page,
                position
            )

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
        })

        if len(results) >= MAX_RESULTS:
            break

    return results


# ============================================================
# PARSE DUCKDUCKGO LITE
# ============================================================

def parse_lite_results(page):

    results = []

    patterns = [

        r'<a[^>]+class=["\'][^"\']*result-link[^"\']*["\']'
        r'[^>]+href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',

        r'<a[^>]+href=["\']([^"\']+)["\']'
        r'[^>]+class=["\'][^"\']*result-link[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</a>',
    ]

    matches = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            page,
            flags=re.I | re.S
        )

        if matches:
            break

    for href, title_html in matches:

        title = clean_html(
            title_html
        )

        url = decode_url(
            href
        )

        if not title:
            continue

        if not url.startswith(
            ("http://", "https://")
        ):
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": "",
        })

        if len(results) >= MAX_RESULTS:
            break

    return results


# ============================================================
# DIRECT DUCKDUCKGO SEARCH
# ============================================================

def duckduckgo_search(query):

    query = query.strip()

    if not query:
        return []

    encoded = urllib.parse.urlencode({
        "q": query,
        "kl": "us-en",
        "kp": "-1",
    })

    search_urls = [

        "https://html.duckduckgo.com/html/?"
        + encoded,

        "https://lite.duckduckgo.com/lite/?"
        + encoded,
    ]

    headers = {
        "User-Agent": USER_AGENT,

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),

        "Accept-Language":
            "en-US,en;q=0.9",

        "Cache-Control":
            "no-cache",

        "Pragma":
            "no-cache",
    }

    last_error = ""

    for search_url in search_urls:

        try:

            status(
                "[Searching DuckDuckGo...]",
                "cyan"
            )

            request = urllib.request.Request(
                search_url,
                headers=headers,
                method="GET"
            )

            with urllib.request.urlopen(
                request,
                timeout=SEARCH_TIMEOUT
            ) as response:

                page = response.read().decode(
                    "utf-8",
                    errors="replace"
                )

            if not page:
                continue

            # ----------------------------------------------
            # Standard parser
            # ----------------------------------------------

            results = parse_standard_results(
                page
            )

            if results:
                for result in results:
                    result["engine"] = "DuckDuckGo"
                return results

            # ----------------------------------------------
            # Lite parser
            # ----------------------------------------------

            results = parse_lite_results(
                page
            )

            if results:
                for result in results:
                    result["engine"] = "DuckDuckGo"
                return results

        except urllib.error.HTTPError as e:

            last_error = (
                f"HTTP {e.code}: {e.reason}"
            )

            status(
                f"[{last_error}]",
                "red"
            )

        except urllib.error.URLError as e:

            last_error = (
                f"Network error: {e.reason}"
            )

            status(
                f"[{last_error}]",
                "red"
            )

        except Exception as e:

            last_error = str(e)

            status(
                f"[Search error: {last_error}]",
                "red"
            )

    if last_error:

        status(
            f"[Search failed: {last_error}]",
            "red"
        )

    return []


# ============================================================
# STARTPAGE SEARCH
# ============================================================

def startpage_search(query):

    query = query.strip()

    if not query:
        return []

    encoded = urllib.parse.urlencode({
        "query": query,
        "cat": "web",
        "pl": "opensearch"
    })

    search_url = "https://www.startpage.com/sp/search?" + encoded

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    try:

        status(
            "[Searching Startpage...]",
            "cyan"
        )

        request = urllib.request.Request(
            search_url,
            headers=headers,
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=SEARCH_TIMEOUT
        ) as response:

            page = response.read().decode(
                "utf-8",
                errors="replace"
            )

        if not page:
            return []

        results = []

        patterns = [
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*w-gl__result-title[^"\']*["\'][^>]*>(.*?)</a>',
            r'<a[^>]+class=["\'][^"\']*w-gl__result-title[^"\']*["\'][^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        ]

        matches = []

        for pattern in patterns:

            matches = re.findall(
                pattern,
                page,
                flags=re.I | re.S
            )

            if matches:
                break

        for href, title_html in matches:

            title = clean_html(
                title_html
            )

            url = html.unescape(
                href
            )

            if url.startswith("/"):
                url = urllib.parse.urljoin(
                    "https://www.startpage.com",
                    url
                )

            if (
                "startpage.com" in url
                and (
                    "/sp/" in url
                    or "query=" in url
                )
            ):
                continue

            if not title:
                continue

            if not url.startswith(
                ("http://", "https://")
            ):
                continue

            if len(title) < 3:
                continue

            results.append({
                "title": title,
                "url": decode_url(url),
                "snippet": "",
                "engine": "Startpage",
            })

            if len(results) >= MAX_RESULTS:
                break

        return results

    except urllib.error.HTTPError as e:

        status(
            f"[Startpage HTTP {e.code}: {e.reason}]",
            "red"
        )

    except urllib.error.URLError as e:

        status(
            f"[Startpage network error: {e.reason}]",
            "red"
        )

    except Exception as e:

        status(
            f"[Startpage error: {e}]",
            "red"
        )

    return []


# ============================================================
# WEBPAGE EXTRACTION
# ============================================================

class PageTextExtractor(HTMLParser):

    def __init__(self):

        super().__init__(
            convert_charrefs=True
        )

        self.parts = []
        self.links = []
        self.skip_depth = 0
        self.current_href = None
        self.current_link_text = []

        self.skip_tags = {
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "nav",
            "footer",
            "form",
            "aside"
        }

    def handle_starttag(
        self,
        tag,
        attrs
    ):

        attrs = dict(attrs)

        if tag in self.skip_tags:

            self.skip_depth += 1

            return

        if self.skip_depth:
            return

        if tag == "a" and attrs.get("href"):

            self.current_href = attrs.get(
                "href"
            )

            self.current_link_text = []

        if tag in {
            "p",
            "div",
            "article",
            "section",
            "main",
            "header",
            "h1",
            "h2",
            "h3",
            "h4",
            "li",
            "br"
        }:

            self.parts.append(
                "\n"
            )

    def handle_endtag(
        self,
        tag
    ):

        if tag in self.skip_tags:

            if self.skip_depth:
                self.skip_depth -= 1

            return

        if self.skip_depth:
            return

        if tag == "a" and self.current_href:

            text = clean_html(
                " ".join(
                    self.current_link_text
                )
            )

            if text:

                self.links.append(
                    (
                        self.current_href,
                        text
                    )
                )

            self.current_href = None
            self.current_link_text = []

        if tag in {
            "p",
            "div",
            "article",
            "section",
            "main",
            "header",
            "h1",
            "h2",
            "h3",
            "h4",
            "li"
        }:

            self.parts.append(
                "\n"
            )

    def handle_data(
        self,
        data
    ):

        if self.skip_depth:
            return

        text = data.strip()

        if not text:
            return

        self.parts.append(
            text + " "
        )

        if self.current_href is not None:

            self.current_link_text.append(
                text
            )


def fetch_webpage(url):

    if not url.startswith(
        ("http://", "https://")
    ):

        return "", []

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    try:

        request = urllib.request.Request(
            url,
            headers=headers,
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=SEARCH_TIMEOUT
        ) as response:

            content_type = response.headers.get(
                "Content-Type",
                ""
            )

            if (
                "text/html"
                not in content_type.lower()
                and
                "application/xhtml"
                not in content_type.lower()
            ):

                return "", []

            raw = response.read(
                2_000_000
            ).decode(
                "utf-8",
                errors="replace"
            )

        parser = PageTextExtractor()

        parser.feed(
            raw
        )

        text = clean_html(
            " ".join(
                parser.parts
            )
        )

        return (
            text[:PAGE_CHAR_LIMIT],
            parser.links
        )

    except Exception:
        return "", []


def choose_followup_links(
    base_url,
    links,
    query
):

    base = urllib.parse.urlparse(
        base_url
    )

    query_terms = [
        x.lower()
        for x in re.findall(
            r"[a-zA-Z0-9]{4,}",
            query
        )
    ]

    scored = []
    seen = set()

    for href, text in links:

        full = urllib.parse.urljoin(
            base_url,
            href
        )

        parsed = urllib.parse.urlparse(
            full
        )

        if parsed.scheme not in (
            "http",
            "https"
        ):
            continue

        if parsed.netloc != base.netloc:
            continue

        clean_url = full.split(
            "#",
            1
        )[0]

        if (
            clean_url.rstrip("/")
            ==
            base_url.rstrip("/")
            or
            clean_url in seen
        ):
            continue

        if re.search(
            r"\.(jpg|jpeg|png|gif|webp|svg|mp4|mp3|zip|exe|css|js)(\?|$)",
            parsed.path,
            re.I
        ):
            continue

        seen.add(
            clean_url
        )

        haystack = (
            text
            + " "
            + parsed.path
        ).lower()

        score = sum(
            2
            for term in query_terms
            if term in haystack
        )

        if any(
            word in haystack
            for word in (
                "source",
                "original",
                "study",
                "research",
                "report",
                "details",
                "documentation",
                "docs",
                "announcement"
            )
        ):

            score += 4

        if parsed.netloc == base.netloc:
            score += 1

        scored.append(
            (
                score,
                clean_url
            )
        )

    scored.sort(
        reverse=True
    )

    return [
        url
        for _, url in scored[:LINKS_PER_PAGE]
    ]


def enrich_with_webpages(
    results,
    query
):

    if not results:
        return results

    enriched = []
    seen_pages = set()
    total_chars = 0

    for index, result in enumerate(
        results[:PAGE_FETCH_LIMIT]
    ):

        url = result.get(
            "url",
            ""
        )

        if (
            not url
            or
            url in seen_pages
        ):
            continue

        seen_pages.add(
            url
        )

        status(
            f"[Reading webpage {index + 1}/{min(len(results), PAGE_FETCH_LIMIT)}]",
            "cyan"
        )

        text, links = fetch_webpage(
            url
        )

        if text:

            result["page_content"] = text

            total_chars += len(
                text
            )

        enriched.append(
            result
        )

        if total_chars >= TOTAL_WEB_CHAR_LIMIT:
            break

        # Level 3: follow up to two relevant links
        # from each important result.
        for linked_url in choose_followup_links(
            url,
            links,
            query
        ):

            if (
                linked_url in seen_pages
                or
                total_chars >= TOTAL_WEB_CHAR_LIMIT
            ):
                continue

            seen_pages.add(
                linked_url
            )

            status(
                "[Reading linked source page...]",
                "cyan"
            )

            linked_text, _ = fetch_webpage(
                linked_url
            )

            if linked_text:

                enriched.append({
                    "title":
                        "Linked page from "
                        + result.get(
                            "title",
                            "source"
                        ),
                    "url":
                        linked_url,
                    "snippet":
                        "",
                    "engine":
                        result.get(
                            "engine",
                            "Web"
                        ),
                    "page_content":
                        linked_text,
                })

                total_chars += len(
                    linked_text
                )

    # Preserve search results that were not fetched.
    for result in results[
        PAGE_FETCH_LIMIT:
    ]:

        if total_chars >= TOTAL_WEB_CHAR_LIMIT:
            break

        enriched.append(
            result
        )

    return enriched


# ============================================================
# MULTI-QUERY SEARCH
# ============================================================
#
# Instead of searching only one vague query, create several
# targeted searches and combine the results.
# ============================================================

def perform_web_search(
    user_prompt
):

    query = make_search_query(
        user_prompt
    )

    is_news = any(
        term in query.lower()
        for term in [
            "news",
            "headline",
            "headlines",
            "breaking",
            "top stories"
        ]
    )

    searches = [
        query
    ]

    if is_news:

        searches.extend([
            query + " latest developments",
            query + " major events",
            query + " analysis",
        ])

    unique_searches = []

    for item in searches:

        item = item.strip()

        if (
            item
            and
            item not in unique_searches
        ):

            unique_searches.append(
                item
            )

    all_results = []
    seen_urls = set()

    for search_query in unique_searches:

        status(
            f"[Query: {search_query}]",
            "cyan"
        )

        # Search both engines.
        engine_results = []

        engine_results.extend(
            duckduckgo_search(
                search_query
            )
        )

        engine_results.extend(
            startpage_search(
                search_query
            )
        )

        for result in engine_results:

            url = result.get(
                "url",
                ""
            )

            if not url:
                continue

            normalized_url = (
                url.rstrip("/")
                .lower()
            )

            if normalized_url in seen_urls:
                continue

            seen_urls.add(
                normalized_url
            )

            all_results.append(
                result
            )

            if len(all_results) >= MAX_RESULTS:
                break

        if len(all_results) >= MAX_RESULTS:
            break

    status(
        f"[Search engines returned {len(all_results)} unique results]",
        "green"
    )

    # Level 3: open important results and follow
    # relevant linked pages.
    return enrich_with_webpages(
        all_results,
        query
    )


# ============================================================
# FORMAT WEB RESULTS
# ============================================================

def web_search(
    user_prompt
):

    results = perform_web_search(
        user_prompt
    )

    if not results:

        status(
            "[WEB SEARCH RETURNED NO RESULTS]",
            "red"
        )

        return ""

    status(
        f"[Found {len(results)} web results]",
        "green"
    )

    output = []

    output.append(
        "LIVE WEB SEARCH RESULTS"
    )

    output.append(
        "========================"
    )

    output.append(
        "The following information was retrieved "
        "from live web searches."
    )

    output.append(
        ""
    )

    for number, result in enumerate(
        results,
        1
    ):

        title = result.get(
            "title",
            ""
        )

        url = result.get(
            "url",
            ""
        )

        snippet = result.get(
            "snippet",
            ""
        )

        output.append(
            f"RESULT {number}"
        )

        output.append(
            f"TITLE: {title}"
        )

        output.append(
            f"URL: {url}"
        )

        engine = result.get(
            "engine",
            "Web"
        )

        output.append(
            f"SEARCH ENGINE: {engine}"
        )

        if snippet:

            output.append(
                f"SNIPPET: {snippet}"
            )

        page_content = result.get(
            "page_content",
            ""
        )

        if page_content:

            output.append(
                "WEBPAGE CONTENT:"
            )

            output.append(
                page_content
            )

        output.append(
            ""
        )

    output.append(
        "END LIVE WEB SEARCH RESULTS"
    )

    return "\n".join(
        output
    )


# ============================================================
# DETERMINE WHETHER WEB SEARCH IS REQUIRED
# ============================================================

def needs_web_search(
    prompt
):

    text = prompt.lower()

    triggers = [

        "search",
        "search the web",
        "search online",
        "look up",
        "look online",
        "find online",
        "find on the web",
        "internet",
        "web results",

        "today",
        "tonight",
        "yesterday",
        "tomorrow",
        "right now",
        "currently",
        "current",
        "latest",
        "recent",
        "recently",
        "this week",
        "this month",
        "this year",

        "news",
        "headline",
        "headlines",
        "breaking",
        "top stories",
        "top news",
        "latest news",

        "weather",
        "forecast",

        "what happened",
        "what's happening",
        "what is happening",

        "2026",
    ]

    return any(
        trigger in text
        for trigger in triggers
    )


# ============================================================
# CREATE SEARCH QUERY
# ============================================================

def make_search_query(
    prompt
):

    query = prompt.strip()

    query_lower = query.lower()

    remove_phrases = [

        "can you",
        "could you",
        "would you",
        "please",
        "tell me",
        "tell me about",
        "what are",
        "what is",
        "what's",
        "give me",
        "show me",
        "search for",
        "search the web for",
        "search online for",
        "look up",
        "look online for",
        "find information about",
        "find information on",
        "find online",
    ]

    for phrase in remove_phrases:

        query_lower = query_lower.replace(
            phrase,
            ""
        )

    query_lower = re.sub(
        r"\s+",
        " ",
        query_lower
    ).strip()

    if not query_lower:

        query_lower = query

    # --------------------------------------------------------
    # Current year.
    # --------------------------------------------------------

    current_year = str(
        datetime.now().year
    )

    current_terms = [

        "today",
        "latest",
        "current",
        "recent",
        "news",
        "headline",
        "headlines",
        "breaking",
        "top stories",
    ]

    if (
        any(
            term in query_lower
            for term in current_terms
        )
        and
        current_year not in query_lower
    ):

        query_lower += (
            " "
            + current_year
        )

    return query_lower


# ============================================================
# BUILD DETAILED GEMMA PROMPT
# ============================================================

def build_web_prompt(
    user_prompt,
    web_results
):

    # Keep retrieved webpage material capped so that the
    # configured LiteRT-LM context size is not overwhelmed.
    #
    # MODEL_WEB_CHAR_LIMIT remains a conservative fixed limit
    # for the web-search portion of the prompt.
    if len(web_results) > MODEL_WEB_CHAR_LIMIT:

        web_results = web_results[
            :MODEL_WEB_CHAR_LIMIT
        ]

        web_results += (
            "\n\n"
            "[Additional retrieved webpage content omitted "
            "to stay within the model context limit.]"
        )

    return f"""
You are an AI assistant with access to LIVE WEB SEARCH
RESULTS supplied by the application.

The user's question is:

{user_prompt}

You MUST use the web results below as the primary source
for current information.

IMPORTANT:

- Do NOT say that you cannot access the internet.
- Do NOT say that you do not have real-time information.
- Do NOT give a vague generic answer.
- Do NOT invent facts.
- Do NOT invent URLs or sources.
- Use multiple results whenever possible.
- Compare information across different results.
- Use the actual webpage content when available, not only snippets.
- If sources disagree, mention the disagreement.
- If the available results are insufficient, explicitly say what
  information is missing.

DEPTH REQUIREMENT:

Give a detailed, substantive answer based on the retrieved
webpage material. Prefer factual detail over generic commentary.

LIVE WEB SEARCH RESULTS
=======================

{web_results}

=======================

Now answer the user's question using the search results and
webpage content above.
""".strip()


# ============================================================
# MODEL BACKENDS
# ============================================================

def read_model_mode():

    """Read default.txt: 1 = LiteRT-LM, 2 = Ollama/GGUF."""

    try:

        with open(
            DEFAULT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            value = f.read().strip()

    except OSError as e:

        status(
            f"[Could not read {DEFAULT_FILE}: {e}]",
            "red"
        )

        status(
            "[Create default.txt containing 1 or 2.]",
            "yellow"
        )

        sys.exit(1)

    if value not in (
        "1",
        "2"
    ):

        status(
            f"[Invalid {DEFAULT_FILE}: {value!r}. Use 1 or 2.]",
            "red"
        )

        sys.exit(1)

    return int(
        value
    )


def get_ollama_model():

    return os.environ.get(
        "OLLAMA_MODEL",
        OLLAMA_MODEL
    ).strip()


def ollama_generate(
    prompt
):

    """
    Send a prompt to Ollama's local /api/chat endpoint.

    Ollama can serve a GGUF model after that model has been
    imported into Ollama with a Modelfile.
    """

    model = get_ollama_model()

    if not model:

        raise RuntimeError(
            "OLLAMA_MODEL is empty. Set it to the installed "
            "Ollama model name."
        )

    url = (
        OLLAMA_HOST.rstrip("/")
        + "/api/chat"
    )

    payload = {

        "model":
            model,

        "messages": [

            {
                "role":
                    "user",

                "content":
                    prompt
            }
        ],

        "stream":
            False,

        # ----------------------------------------------------
        # GGUF / Ollama token-size control
        # ----------------------------------------------------
        "options": {

            "num_ctx":
                GGUF_TOKEN_SIZE
        }
    }

    request = urllib.request.Request(

        url,

        data=json.dumps(
            payload
        ).encode(
            "utf-8"
        ),

        headers={

            "Content-Type":
                "application/json",

            "Accept":
                "application/json"
        },

        method="POST"
    )

    status(
        f"[Using Ollama model: {model}]",
        "cyan"
    )

    status(
        f"[GGUF token/context size: {GGUF_TOKEN_SIZE}]",
        "cyan"
    )

    with urllib.request.urlopen(
        request,
        timeout=OLLAMA_TIMEOUT
    ) as response:

        raw = response.read().decode(
            "utf-8",
            errors="replace"
        )

    if not raw:

        raise RuntimeError(
            "Ollama returned an empty response."
        )

    result = json.loads(
        raw
    )

    message = result.get(
        "message",
        {}
    )

    if isinstance(
        message,
        dict
    ):

        content = message.get(
            "content",
            ""
        )

        if content:

            return str(
                content
            )

    # Compatibility with Ollama-compatible servers using
    # the /api/generate response shape.

    content = result.get(
        "response",
        ""
    )

    if content:

        return str(
            content
        )

    raise RuntimeError(
        "Ollama returned no assistant text."
    )


def clean_model_response(
    raw_text
):

    """Common response cleanup for both model backends."""

    if raw_text is None:
        return ""

    raw_text = str(
        raw_text
    )

    raw_text = raw_text.replace(
        "\\r\\n",
        "\n"
    )

    raw_text = raw_text.replace(
        "\\n",
        "\n"
    )

    stripped = raw_text.strip()

    # Some model wrappers return a JSON array of text fragments.
    if (
        stripped.startswith("[")
        and
        stripped.endswith("]")
    ):

        try:

            parsed = json.loads(
                stripped
            )

            if isinstance(
                parsed,
                list
            ):

                pieces = []

                for item in parsed:

                    if isinstance(
                        item,
                        dict
                    ):

                        value = item.get(
                            "text"
                        )

                        if value:

                            pieces.append(
                                str(value)
                            )

                    elif isinstance(
                        item,
                        str
                    ):

                        pieces.append(
                            item
                        )

                if pieces:

                    raw_text = "\n".join(
                        pieces
                    )

        except Exception:
            pass

    return raw_text.strip()


def run_litert_model(
    prompt
):

    """Run the existing LiteRT-LM backend."""

    if litert_lm is None:

        raise RuntimeError(
            "litert_lm is not installed, but default.txt contains 1."
        )

    litert_lm.set_min_log_severity(
        litert_lm.LogSeverity.ERROR
    )

    status(
        f"[Using LiteRT-LM: {LITERT_MODEL_PATH}]",
        "cyan"
    )

    status(
        f"[LiteRT-LM token/context size: {LITERT_TOKEN_SIZE}]",
        "cyan"
    )

    with litert_lm.Engine(

        LITERT_MODEL_PATH,

        backend=
            litert_lm.Backend.CPU(),

        # ----------------------------------------------------
        # LiteRT-LM token-size control
        # ----------------------------------------------------
        max_num_tokens=
            LITERT_TOKEN_SIZE

    ) as engine:

        with engine.create_conversation() as conversation:

            response = conversation.send_message(
                prompt
            )

            raw_text = ""

            if isinstance(
                response,
                dict
            ):

                content = response.get(
                    "content"
                )

                if isinstance(
                    content,
                    dict
                ):

                    raw_text = content.get(
                        "text",
                        ""
                    )

                elif content is not None:

                    raw_text = str(
                        content
                    )

            elif hasattr(
                response,
                "text"
            ):

                raw_text = response.text

            else:

                raw_text = str(
                    response
                )

            return clean_model_response(
                raw_text
            )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:

        print(
            'Usage: ask "Your question here"',
            file=sys.stderr
        )

        sys.exit(1)

    user_prompt = " ".join(
        sys.argv[1:]
    ).strip()

    if not user_prompt:

        print(
            "No question supplied.",
            file=sys.stderr
        )

        sys.exit(1)

    # ========================================================
    # MODEL BACKEND
    # ========================================================

    model_mode = read_model_mode()

    if model_mode == 1:

        status(
            "[default.txt = 1 -> LiteRT-LM]",
            "green"
        )

        status(
            f"[Configured LiteRT-LM token size: {LITERT_TOKEN_SIZE}]",
            "green"
        )

    else:

        status(
            "[default.txt = 2 -> Ollama / GGUF]",
            "green"
        )

        status(
            f"[Configured GGUF token size: {GGUF_TOKEN_SIZE}]",
            "green"
        )

    final_input_text = user_prompt

    # ========================================================
    # WEB
    # ========================================================

    if needs_web_search(
        user_prompt
    ):

        search_query = make_search_query(
            user_prompt
        )

        status(
            f"[Searching the web: {search_query}]",
            "yellow"
        )

        web_results = web_search(
            user_prompt
        )

        if web_results:

            final_input_text = build_web_prompt(
                user_prompt,
                web_results
            )

        else:

            final_input_text = f"""
The application attempted a live web search but received
no usable web results.

Do not invent current information.

Tell the user that the live web search failed.

USER QUESTION:
{user_prompt}
""".strip()

    # ========================================================
    # RUN SELECTED MODEL
    # ========================================================

    try:

        if model_mode == 1:

            raw_text = run_litert_model(
                final_input_text
            )

        else:

            raw_text = ollama_generate(
                final_input_text
            )

        if not raw_text:

            print(
                "No response generated.",
                file=sys.stderr
            )

            sys.exit(1)

        print(
            raw_text
        )

    except urllib.error.HTTPError as e:

        print(
            f"Model HTTP error: {e.code}: {e.reason}",
            file=sys.stderr
        )

        if model_mode == 2:

            print(
                "[Make sure Ollama is running and the model "
                "name is installed.]",
                file=sys.stderr
            )

        sys.exit(1)

    except urllib.error.URLError as e:

        print(
            f"Model connection error: {e.reason}",
            file=sys.stderr
        )

        if model_mode == 2:

            print(
                f"[Could not connect to Ollama at {OLLAMA_HOST}]",
                file=sys.stderr
            )

        sys.exit(1)

    except Exception as e:

        if model_mode == 1:

            print(
                f"LiteRT-LM error: {e}",
                file=sys.stderr
            )

        else:

            print(
                f"Ollama/GGUF error: {e}",
                file=sys.stderr
            )

        sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()