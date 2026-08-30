#!/usr/bin/env python3

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import html
from datetime import datetime

import litert_lm


# ============================================================
# SETTINGS
# ============================================================

MAX_RESULTS = 10
SEARCH_TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0.0.0 Mobile Safari/537.36"
)


# ============================================================
# STATUS OUTPUT
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
# HTML CLEANING
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
# URL CLEANING
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

        # DuckDuckGo redirect URL.
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
    start_position
):

    # Search a reasonable amount of HTML following
    # the result title.

    section = page[
        start_position:
        start_position + 6000
    ]

    patterns = [

        r'class=["\']result__snippet["\'][^>]*>'
        r'(.*?)'
        r'</',

        r'class=["\'][^"\']*result__snippet[^"\']*["\'][^>]*>'
        r'(.*?)'
        r'</',

        r'class=["\']result-snippet["\'][^>]*>'
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
# PARSE DUCKDUCKGO HTML RESULTS
# ============================================================

def parse_duckduckgo_html(page):

    results = []

    # --------------------------------------------------------
    # Format used by DuckDuckGo HTML results.
    # --------------------------------------------------------

    patterns = [

        r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\']'
        r'[^>]+href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',

        r'<a[^>]+href=["\']([^"\']+)["\']'
        r'[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]*>'
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

        # Find where this title occurs in the page so
        # we can locate its snippet.

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

def parse_duckduckgo_lite(page):

    results = []

    # Lite results commonly use result-link.

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

    urls = [

        # HTML search.
        "https://html.duckduckgo.com/html/?"
        + encoded,

        # Lite search.
        "https://lite.duckduckgo.com/lite/?"
        + encoded,

        # No-AI search.
        "https://noai.duckduckgo.com/?"
        + encoded,

        # Normal search as final fallback.
        "https://duckduckgo.com/?"
        + encoded,
    ]

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    }

    last_error = ""

    for search_url in urls:

        try:

            status(
                "[Trying DuckDuckGo...]",
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

            # ------------------------------------------------
            # HTML parser.
            # ------------------------------------------------

            results = parse_duckduckgo_html(
                page
            )

            if results:
                return results

            # ------------------------------------------------
            # Lite parser.
            # ------------------------------------------------

            results = parse_duckduckgo_lite(
                page
            )

            if results:
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
            f"[All search methods failed: {last_error}]",
            "red"
        )

    return []


# ============================================================
# NEWS SEARCH
#
# DuckDuckGo's normal HTML search can be used with news
# keywords. This avoids third-party Python packages.
# ============================================================

def news_search(query):

    year = str(
        datetime.now().year
    )

    query_lower = query.lower()

    if year not in query_lower:

        query = (
            query
            + " "
            + year
        )

    # Search multiple formulations if needed.

    searches = [
        query,
        query + " latest",
        query + " today",
    ]

    all_results = []

    seen_urls = set()

    for search_query in searches:

        results = duckduckgo_search(
            search_query
        )

        for result in results:

            url = result.get(
                "url",
                ""
            )

            if not url:
                continue

            if url in seen_urls:
                continue

            seen_urls.add(url)

            all_results.append(
                result
            )

            if len(all_results) >= MAX_RESULTS:
                break

        if len(all_results) >= MAX_RESULTS:
            break

    return all_results


# ============================================================
# WEB SEARCH
# ============================================================

def web_search(query):

    query = query.strip()

    if not query:
        return ""

    is_news = any(
        phrase in query.lower()
        for phrase in [
            "news",
            "headline",
            "headlines",
            "top stories",
            "breaking",
        ]
    )

    if is_news:

        results = news_search(
            query
        )

    else:

        results = duckduckgo_search(
            query
        )

    if not results:

        status(
            "[WEB SEARCH RETURNED NO RESULTS]",
            "red"
        )

        return ""

    # ========================================================
    # FORMAT RESULTS FOR GEMMA
    # ========================================================

    output = []

    output.append(
        "LIVE WEB SEARCH RESULTS"
    )

    output.append(
        "========================"
    )

    output.append(
        "These are actual results returned "
        "by the application's web search."
    )

    output.append("")

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

        if snippet:

            output.append(
                f"SNIPPET: {snippet}"
            )

        output.append("")

    output.append(
        "END LIVE WEB SEARCH RESULTS"
    )

    return "\n".join(
        output
    )


# ============================================================
# WEB SEARCH DETECTION
# ============================================================

def needs_web_search(prompt):

    text = prompt.lower()

    triggers = [

        # Explicit search.
        "search",
        "search the web",
        "search online",
        "look up",
        "look online",
        "find online",
        "find on the web",
        "internet",
        "web results",

        # Current information.
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

        # News.
        "news",
        "headline",
        "headlines",
        "breaking",
        "top stories",
        "top news",
        "latest news",

        # Weather.
        "weather",
        "forecast",

        # Current events.
        "what happened",
        "what's happening",
        "what is happening",

        # Current year.
        "2026",
    ]

    return any(
        item in text
        for item in triggers
    )


# ============================================================
# SEARCH QUERY CLEANUP
# ============================================================

def make_search_query(prompt):

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
    # Add current year to current/news searches.
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
        and current_year not in query_lower
    ):

        query_lower += (
            " "
            + current_year
        )

    return query_lower


# ============================================================
# BUILD WEB-AWARE GEMMA PROMPT
# ============================================================

def build_web_prompt(
    user_prompt,
    web_results
):

    return f"""
You have been given LIVE WEB SEARCH RESULTS by the
application.

IMPORTANT:

The application performed the web search for you.

You MUST use the supplied web results to answer the
user's question.

Do NOT say that you lack internet access.

Do NOT say that you cannot access real-time information.

Do NOT say that you do not have live news feeds.

Do NOT ignore the supplied search results.

Do NOT invent facts that are not supported by the
search results.

If the search results are incomplete, clearly say that
the available search results were incomplete.

When the user asks about current events, today's news,
recent information, or other time-sensitive information,
prioritize the supplied search results.

Use the URLs and snippets as evidence.

LIVE WEB SEARCH RESULTS
=======================

{web_results}

=======================

USER QUESTION
=============

{user_prompt}

=======================

Answer the user's question using the supplied live
web search results.
""".strip()


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
    # MODEL
    # ========================================================

    model_path = (
        "/storage/emulated/0/"
        "gemma-4-E2B-it.litertlm"
    )

    # ========================================================
    # LITERT SETTINGS
    # ========================================================

    litert_lm.set_min_log_severity(
        litert_lm.LogSeverity.ERROR
    )

    # ========================================================
    # DEFAULT PROMPT
    # ========================================================

    final_input_text = user_prompt

    # ========================================================
    # WEB SEARCH
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
            search_query
        )

        if web_results:

            status(
                "[Web search succeeded]",
                "green"
            )

            final_input_text = build_web_prompt(
                user_prompt,
                web_results
            )

        else:

            status(
                "[Web search failed]",
                "red"
            )

            # ------------------------------------------------
            # Do NOT allow the offline model to fabricate
            # current information.
            # ------------------------------------------------

            final_input_text = f"""
The application attempted a live web search for the
following question:

{user_prompt}

The live web search returned no usable results.

Do not invent current information.

Do not pretend that you know today's news.

Tell the user briefly that the live web search failed
and that no current search results were available.
""".strip()

    # ========================================================
    # LITERT-LM
    # ========================================================

    try:

        with litert_lm.Engine(
            model_path,
            backend=litert_lm.Backend.CPU()
        ) as engine:

            with engine.create_conversation() as conversation:

                response = conversation.send_message(
                    final_input_text
                )

                # =================================================
                # EXTRACT RESPONSE TEXT
                # =================================================

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

                # =================================================
                # EMPTY RESPONSE
                # =================================================

                if not raw_text:

                    print(
                        "No response generated.",
                        file=sys.stderr
                    )

                    sys.exit(1)

                # =================================================
                # FIX ESCAPED NEWLINES
                # =================================================

                raw_text = raw_text.replace(
                    "\\r\\n",
                    "\n"
                )

                raw_text = raw_text.replace(
                    "\\n",
                    "\n"
                )

                # =================================================
                # HANDLE JSON RESPONSE
                # =================================================

                stripped = raw_text.strip()

                if (
                    stripped.startswith("[")
                    and stripped.endswith("]")
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

                                    text = item.get(
                                        "text"
                                    )

                                    if text:

                                        pieces.append(
                                            str(text)
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

                # =================================================
                # FINAL OUTPUT
                # =================================================

                print(
                    raw_text.strip()
                )

    except Exception as e:

        print(
            f"LiteRT-LM error: {e}",
            file=sys.stderr
        )

        sys.exit(1)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()

