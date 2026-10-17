"""
Why a social profile page gave no posts: login wall, captcha, or plain empty.

Two rules:

1. Positive evidence first. A page that rendered post cards is a normal page,
   and nothing here runs in that case. Page HTML carries creators' captions and
   comments, so matching words like "验证" or "登录" against the whole page
   flags healthy accounts as blocked.

2. Empty is not success. When no posts were found, raise FetchBlocked so the
   run is reported as failed with a reason instead of "0 new articles".
"""

import logging

from generators.base import FetchBlocked

logger = logging.getLogger(__name__)

KIND_LOGIN = "login"
KIND_CAPTCHA = "captcha"
KIND_EMPTY = "empty"

_MESSAGE = {
    KIND_LOGIN: "login expired, run the platform's --login again",
    KIND_CAPTCHA: "the platform asked for a security check, try again later",
    KIND_EMPTY: "no posts found (account has no visible posts, or the page did not load)",
}

# URL fragments of login / passport pages the platforms redirect to.
_LOGIN_URL_MARKERS = (
    "/login", "/passport", "passport.", "/signin", "/newlogin",
    "accounts.google.com", "servicelogin", "website-login",
)
# Text only shown on anti-bot pages. Keep these specific: generic words like
# "captcha" also appear in the JS/CSS of normal pages.
_ANTIBOT_MARKERS = (
    "验证码中间页", "IP存在风险", "安全限制", "访问验证",
    '"result":2,"error_msg"', "unusual traffic detected",
)


def diagnose_empty_page(page) -> tuple[str, str]:
    """Classify a page that yielded no posts. Returns (kind, detail).

    Only call this when no content was found (see rule 1 above).
    """
    url = getattr(page, "url", "") or ""
    low_url = url.lower()
    try:
        html = page.html or ""
    except Exception:
        html = ""

    # Xiaohongshu's captcha page is /website-login/captcha: check before login URLs.
    if "captcha" in low_url:
        return KIND_CAPTCHA, f"captcha url: {url[:80]}"
    for m in _LOGIN_URL_MARKERS:
        if m in low_url:
            return KIND_LOGIN, f"login url: {url[:80]}"
    for m in _ANTIBOT_MARKERS:
        if m in html:
            return KIND_CAPTCHA, f"anti-bot marker: {m}"
    return KIND_EMPTY, f"no posts at {url[:80]}"


def raise_no_content(platform: str, page):
    """Call when a profile page yielded no posts. Always raises FetchBlocked."""
    kind, detail = diagnose_empty_page(page)
    logger.warning("%s got no content: %s (%s)", platform, kind, detail)
    raise FetchBlocked(platform, kind, _MESSAGE[kind])
