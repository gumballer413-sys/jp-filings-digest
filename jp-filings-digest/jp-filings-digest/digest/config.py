"""Settings. Every value can be overridden with an environment variable of the same name."""

import os
from dataclasses import dataclass, field

# EDINET docTypeCode -> (English label, priority; lower number = shown first)
DOC_TYPES = {
    "240": ("Tender offer filing", 0),
    "270": ("Tender offer result report", 1),
    "290": ("Target's opinion on tender offer", 1),
    "180": ("Extraordinary report", 2),
    "350": ("Large shareholding report (5% rule)", 3),
    "360": ("Change report (5% rule)", 3),
    "220": ("Share buyback status report", 5),
}

# Words that would turn a fact summary into investment advice or hype.
#   Matched as whole words, case-insensitive. Plain facts such as "share buyback"
#   or "offer to acquire shares" are allowed; opinions and calls to act are not.
BANNED_PHRASES = [
#   "recommend" is NOT banned: a target board recommending a tender offer is a fact.
    "should buy", "should sell", "strong buy", "buy rating", "sell rating",
    "undervalued", "overvalued", "bullish", "bearish", "investment opportunity",
    "should invest", "price target", "cheap stock", "must-watch", "moonshot",
    "likely to rise", "likely to fall", "stock will rise", "stock will fall",
]


@dataclass
class Settings:
    edinet_api_key: str = field(default_factory=lambda: (os.environ.get("EDINET_API_KEY") or ""))
    anthropic_api_key: str = field(default_factory=lambda: (os.environ.get("ANTHROPIC_API_KEY") or ""))
    model: str = field(default_factory=lambda: (os.environ.get("MODEL") or "claude-haiku-5-5"))
    max_docs: int = field(default_factory=lambda: int((os.environ.get("MAX_DOCS") or "150")))
    request_interval_sec: float = field(default_factory=lambda: float((os.environ.get("REQUEST_INTERVAL_SEC") or "3")))
    max_input_chars: int = field(default_factory=lambda: int((os.environ.get("MAX_INPUT_CHARS") or "12000")))
    site_title: str = field(default_factory=lambda: (os.environ.get("SITE_TITLE") or "Japan Small-Cap Filings in English"))
    site_url: str = field(default_factory=lambda: (os.environ.get("SITE_URL") or "https://example.github.io/jp-filings-digest"))
    operator_name: str = field(default_factory=lambda: (os.environ.get("OPERATOR_NAME") or "the operator of this site"))
    contact_email: str = field(default_factory=lambda: (os.environ.get("CONTACT_EMAIL") or ""))
    subscribe_url: str = field(default_factory=lambda: (os.environ.get("SUBSCRIBE_URL") or ""))
