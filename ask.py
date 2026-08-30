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

MAX_RESULTS = 15
SEARCH_TIMEOUT = 20

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
                return results

            # ----------------------------------------------
            # Lite parser
            # ----------------------------------------------

            results = parse_lite_results(
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
            f"[Search failed: {last_error}]",
            "red"
        )

    return []


# ============================================================
# MULTI-QUERY SEARCH
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

    searches = []

    # --------------------------------------------------------
    # Main query
    # --------------------------------------------------------

    searches.append(
        query
    )

    # --------------------------------------------------------
    # For news/current events, search several angles.
    # --------------------------------------------------------

    if is_news:

        searches.append(
            query + " latest developments"
        )

        searches.append(
            query + " major events"
        )

        searches.append(
            query + " analysis"
        )

    # --------------------------------------------------------
    # Remove duplicate search strings.
    # --------------------------------------------------------

    unique_searches = []

    for item in searches:

        item = item.strip()

        if (
            item
            and item not in unique_searches
        ):

            unique_searches.append(
                item
            )

    all_results = []

    seen_urls = set()

    # --------------------------------------------------------
    # Run searches.
    # --------------------------------------------------------

    for search_query in unique_searches:

        status(
            f"[Query: {search_query}]",
            "cyan"
        )

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

            # Avoid duplicate pages.

            normalized_url = url.rstrip(
                "/"
            ).lower()

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

    return all_results


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
        and current_year not in query_lower
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
- Do NOT say that you lack live news feeds.
- Do NOT give a vague generic answer.
- Do NOT simply repeat one search result.
- Do NOT invent facts.
- Do NOT invent URLs or sources.
- Use multiple results whenever possible.
- Compare information across different results.
- Explain the important details.
- Include relevant dates.
- Explain what happened, who was involved, where it
  happened, and why it matters when that information is
  available.
- For news, distinguish individual stories instead of
  combining everything into one vague paragraph.
- If sources disagree, mention the disagreement.
- If the available results are insufficient, explicitly
  say what information is missing.

DEPTH REQUIREMENT:

Give a detailed, substantive answer.

For a news request, provide:

1. A concise overview of the major stories.
2. Separate sections for the most important stories.
3. What happened.
4. The key people, organizations, or countries involved.
5. Important dates and numbers when available.
6. Why each story matters.
7. Relevant background or context from the search results.
8. What is known versus what remains uncertain.
9. Source URLs at the end of the relevant sections.

Do not make the answer unnecessarily repetitive, but
prefer depth over a short generic response.

LIVE WEB SEARCH RESULTS
=======================

{web_results}

=======================

Now answer the user's question in detail using the
search results above.
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
    # LITERT
    # ========================================================

    litert_lm.set_min_log_severity(
        litert_lm.LogSeverity.ERROR
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

            # ------------------------------------------------
            # Prevent the model from fabricating current
            # information when web search failed.
            # ------------------------------------------------

            final_input_text = f"""
The application attempted a live web search but received
no usable web results.

Do not invent current information.

Tell the user that the live web search failed.

USER QUESTION:
{user_prompt}
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
                # EXTRACT TEXT
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
                # HANDLE EMPTY RESPONSE
                # =================================================

                if not raw_text:

                    print(
                        "No response generated.",
                        file=sys.stderr
                    )

                    sys.exit(1)

                # =================================================
                # CLEAN ESCAPED NEWLINES
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
                # OUTPUT
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

 