"""The `fetch` tool, served to the model as an MCP tool server.

Verifiers starts this module as its own process (`python -m workbook_tasks.tools`)
on the evaluator, once per environment worker, and the harness reaches it over MCP.
"""

from __future__ import annotations

import asyncio
import html
import os
import re
import urllib.request

import verifiers.v1 as vf

USER_AGENT = os.environ.get("WORKBOOK_TASKS_USER_AGENT", "workbook-tasks/0.2")
MAX_CHARS = 20000


def fetch(url: str) -> str:
    """Fetch a public web page or API response and return its text.

    Args:
        url: The full http(s) address to read.

    Returns:
        The page as plain text, cut to 20,000 characters.
    """
    if not url.startswith(("http://", "https://")):
        return "error: only http(s) addresses can be fetched"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(4_000_000).decode(resp.headers.get_content_charset() or "utf-8", "replace")
    except Exception as e:  # the model sees the error and can try another address
        return f"error: {e}"
    if "<html" in body[:2000].lower():
        body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
        body = html.unescape(re.sub(r"<[^>]+>", " ", body))
        body = re.sub(r"[ \t\r\f\v]+", " ", body)
        body = re.sub(r"\n\s*\n+", "\n", body)
    return body[:MAX_CHARS]


class FetchToolset(vf.Toolset[vf.SharedToolsetConfig]):
    TOOL_PREFIX = None  # advertise the tool as plain `fetch`

    @vf.tool
    async def fetch(self, url: str) -> str:
        """Fetch a public web page or API response and return its text, cut to 20,000 characters.

        Args:
            url: The full http(s) address to read.
        """
        # urllib blocks; a thread keeps one rollout's slow page from stalling the others.
        return await asyncio.to_thread(fetch, url)


if __name__ == "__main__":
    FetchToolset.run()
