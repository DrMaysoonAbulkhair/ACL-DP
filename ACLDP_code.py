#!/usr/bin/env python3
"""
ACL-DP end-to-end computational audit and analysis pipeline
==========================================================

Purpose
-------
This script provides an executable workflow for:

1. acquiring observable cookie-consent interface evidence with Playwright;
2. reconstructing Layer-1 and, where observable, Layer-2 consent pathways;
3. deriving the raw ACL-DP audit variables;
4. constructing the final EE, AE, and CL mechanism indicators/scores;
5. producing the final ACL-DP composite score; and
6. reproducing descriptive, correlation, and threshold-sensitivity outputs.

FINAL SCORING DEFINITION
------------------------
EFFORT_SCORE =
    MECH_EE_ClickAsymmetry
    + MECH_EE_HiddenReject

ATTENTION_SCORE =
    MECH_AE_PrimaryAccept
    + MECH_AE_ProminenceAsymmetry

COGNITIVE_LOAD_SCORE =
    MECH_CL_HighComplexity
    + MECH_CL_HighInfoDensity
    + MECH_CL_GermaneSuppression

ACLDP_TOTAL_SCORE =
    EFFORT_SCORE
    + ATTENTION_SCORE
    + COGNITIVE_LOAD_SCORE

Theoretical ACLDP_TOTAL_SCORE range: 0--7.

MECH_CL_HighToggleVolume is retained for descriptive/sensitivity analysis
but is NOT included in the final COGNITIVE_LOAD_SCORE.

Adaptive behavior (AA), when observed, is retained as supplementary evidence
and is NOT included in ACLDP_TOTAL_SCORE.

IMPORTANT CONSTRUCT-VALIDITY NOTE
---------------------------------
The CL indicators are interface-level proxies. They characterize observable
interface complexity, information density, and explanatory-support conditions.
They do not directly measure users' experienced cognitive workload.

IMPORTANT REPRODUCIBILITY NOTE
------------------------------
The analysis mode reproduces the final ACL-DP scoring from an existing audit
dataset using deterministic rules. The acquisition mode below is an executable,
documented browser-audit implementation for collecting the required observable
variables. If a historical manuscript dataset was collected with an earlier
private/legacy crawler, this reconstructed acquisition implementation should not
be described as the exact historical acquisition code unless that provenance
has been verified by the author.

Examples
--------
Install:
    pip install pandas numpy scipy statsmodels playwright
    playwright install chromium

Audit websites:
    python ACLDP_code.py audit --input domains.txt \
        --output dataset/acldp_audit_raw.csv \
        --screenshots artifacts/screenshots \
        --evidence artifacts/evidence \
        --headless

Analyze an existing anonymized dataset:
    python ACLDP_code.py analyze \
        --input dataset/acldp_dataset_anonymized.csv \
        --results results

Run acquisition + analysis:
    python ACLDP_code.py all --input domains.txt \
        --output dataset/acldp_audit_raw.csv \
        --results results --headless
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import sys
import time
import uuid
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=UserWarning)

try:
    from playwright.async_api import (
        async_playwright,
        Browser,
        BrowserContext,
        Frame,
        Page,
        TimeoutError as PlaywrightTimeoutError,
    )
except Exception:
    async_playwright = None
    Browser = BrowserContext = Frame = Page = Any

VERSION = "2.0.0"

# ---------------------------------------------------------------------
# Final ACL-DP thresholds aligned with the revised manuscript/codebook.
# ---------------------------------------------------------------------
BASE_COMPLEXITY_THRESHOLD = 20
BASE_INFO_DENSITY_THRESHOLD = 4

# Historical manuscript sensitivity values for toggle-volume analysis.
TOGGLE_SENSITIVITY_THRESHOLDS = (8.0, 13.0, 21.4)
COMPLEXITY_SENSITIVITY_THRESHOLDS = (16, 20, 24)
INFO_DENSITY_SENSITIVITY_THRESHOLDS = (3, 4, 5)

DEFAULT_VIEWPORT = {"width": 1366, "height": 768}
DEFAULT_LOCALE = "en-US"
DEFAULT_TIMEZONE = "Asia/Riyadh"
DEFAULT_TIMEOUT_MS = 20_000
DEFAULT_SETTLE_MS = 2_000

AUDIT_COLUMNS = [
    "Website_ID",
    "Domain",
    "URL_Accessed",
    "Audit_Status",
    "Last_Error",
    "Retry_Count",
    "Audit_Level",
    "Run_ID",
    "Access_Date_UTC",
    "Country_or_Market_Observed",
    "Access_Locale",
    "Browser",
    "Headless_Audit",
    "Cookie_Banner_Present",
    "Banner_Type",
    "Consent_Layer_Depth",
    "CMP_Vendor",
    "CMP_Evidence",
    "IAB_TCF_Mentioned",
    "TCF_Evidence",
    "L1_Evidence_Quote",
    "L1_Screenshot_Ref",
    "L1_Accept_All_Present",
    "L1_Reject_All_Present",
    "L1_Manage_Preferences_Present",
    "Accept_Click_Count",
    "Reject_Click_Count",
    "Manage_Click_Count",
    "EE_Click_Asymmetry_RejectMinusAccept",
    "EE_Hidden_Reject_Path",
    "AE_Accept_Button_Prominence_1to3",
    "AE_Reject_Button_Prominence_1to3",
    "AE_Size_Asymmetry_LargerEqualSmaller",
    "AE_Primary_Action_Is_Accept",
    "L2_Available",
    "L2_Evidence_Quote",
    "L2_Screenshot_Ref",
    "L2_Toggle_Count",
    "L2_Vendor_Count",
    "L2_Text_Word_Count",
    "L2_Information_Density_Score_1to5",
    "L2_Germane_Support_Score_1to5",
    "CL_Toggle_Vendor_Complexity_Index",
    "CL_Germane_Suppression_Indicators",
    "AA_RePrompting_After_Reject",
    "AA_RePrompt_Frequency_Observed",
    "SP_Message_ID",
    "SP_Campaign_ID",
    "SP_Variant_Evidence",
    "OT_Purpose_Count",
    "OT_Vendor_Count",
    "Evidence_JSON_Ref",
]

ACCEPT_PATTERNS = [
    r"\baccept all\b",
    r"\ballow all\b",
    r"\bagree(?: to all)?\b",
    r"\baccept cookies\b",
    r"\bconsent to all\b",
]
REJECT_PATTERNS = [
    r"\breject all\b",
    r"\bdecline all\b",
    r"\bdeny all\b",
    r"\breject cookies\b",
    r"\brefuse all\b",
]
MANAGE_PATTERNS = [
    r"\bmanage preferences?\b",
    r"\bcookie settings?\b",
    r"\bprivacy settings?\b",
    r"\bmanage cookies?\b",
    r"\bpreferences?\b",
    r"\bcustomi[sz]e\b",
]
SAVE_PATTERNS = [
    r"\bsave (?:my )?(?:choices|preferences|settings)\b",
    r"\bconfirm (?:my )?(?:choices|preferences|settings)\b",
    r"\bapply (?:choices|preferences|settings)\b",
]
BANNER_KEYWORDS = (
    "cookie",
    "cookies",
    "consent",
    "privacy preferences",
    "privacy preference",
    "tracking",
)
EXPLANATION_KEYWORDS = (
    "purpose",
    "purposes",
    "necessary",
    "functional",
    "analytics",
    "advertising",
    "personalization",
    "vendor",
    "partners",
    "legitimate interest",
    "privacy",
)

CMP_SIGNATURES = {
    "OneTrust": ("onetrust", "optanon"),
    "Didomi": ("didomi",),
    "Cookiebot": ("cookiebot", "cybotcookiebot"),
    "Usercentrics": ("usercentrics", "uc-consent"),
    "TrustArc": ("trustarc", "truste"),
    "Sourcepoint": ("sourcepoint", "sp_message", "sp-message"),
    "Quantcast": ("quantcast", "qc-cmp"),
}

# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Empty URL/domain")
    if not re.match(r"^https?://", value, flags=re.I):
        value = "https://" + value
    return value


def safe_filename(value: str, max_len: int = 90) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value[:max_len].strip("._") or "site"


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def stable_site_id(url: str, idx: int) -> str:
    return f"ACLDP_{idx:04d}"


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12]


def text_matches(text: str, patterns: Sequence[str]) -> bool:
    normalized = " ".join(str(text or "").split()).lower()
    return any(re.search(p, normalized, flags=re.I) for p in patterns)


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def to_binary_yes_no(series: Optional[pd.Series]) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    s = series.astype(str).str.strip().str.lower()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    yes_vals = {"1", "yes", "y", "true", "present", "available"}
    no_vals = {"0", "no", "n", "false", "absent", "not available"}
    out[s.isin(yes_vals)] = 1
    out[s.isin(no_vals)] = 0
    num = pd.to_numeric(series, errors="coerce")
    out[num == 1] = 1
    out[num == 0] = 0
    return out


def find_col(df_cols: Iterable[str], candidates: Sequence[str]) -> Optional[str]:
    cols = list(df_cols)
    df_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in df_map:
            return df_map[cand.lower()]

    def norm(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", s.lower())

    norm_map = {norm(c): c for c in cols}
    for cand in candidates:
        if norm(cand) in norm_map:
            return norm_map[norm(cand)]
    return None


def load_targets(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        tmp = pd.read_csv(path)
        candidates = [
            c for c in tmp.columns
            if c.lower() in {"url", "domain", "website", "url_accessed"}
        ]
        col = candidates[0] if candidates else tmp.columns[0]
        values = tmp[col].dropna().astype(str).tolist()
    else:
        values = [
            line.strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    seen = set()
    out = []
    for value in values:
        try:
            url = normalize_url(value)
        except ValueError:
            continue
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# ---------------------------------------------------------------------
# Browser evidence extraction
# ---------------------------------------------------------------------
@dataclass
class ElementEvidence:
    text: str
    tag: str
    role: str
    frame_url: str
    x: float
    y: float
    width: float
    height: float
    font_size: float
    font_weight: float
    bg: str
    fg: str
    visible: bool
    disabled: bool
    locator_hint: str

    @property
    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)


INTERACTIVE_JS = r"""
() => {
  const els = Array.from(document.querySelectorAll(
    'button, [role="button"], input[type="button"], input[type="submit"], a, [tabindex]'
  ));
  return els.slice(0, 500).map((el, i) => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const text = (
      el.innerText ||
      el.value ||
      el.getAttribute('aria-label') ||
      el.getAttribute('title') ||
      ''
    ).trim();
    const visible = !!(
      r.width > 0 && r.height > 0 &&
      cs.visibility !== 'hidden' &&
      cs.display !== 'none' &&
      parseFloat(cs.opacity || '1') > 0
    );
    let hint = '';
    if (el.id) hint = '#' + CSS.escape(el.id);
    else if (el.getAttribute('data-testid'))
      hint = '[data-testid="' + el.getAttribute('data-testid').replace(/"/g,'\\"') + '"]';
    else if (el.getAttribute('aria-label'))
      hint = '[aria-label="' + el.getAttribute('aria-label').replace(/"/g,'\\"') + '"]';
    else hint = el.tagName.toLowerCase() + ':nth-of-type(' +
      (Array.from(el.parentElement ? el.parentElement.children : []).filter(
        x => x.tagName === el.tagName
      ).indexOf(el) + 1) + ')';

    return {
      text,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      x: r.x, y: r.y, width: r.width, height: r.height,
      font_size: parseFloat(cs.fontSize || '0') || 0,
      font_weight: parseFloat(cs.fontWeight || '400') || 400,
      bg: cs.backgroundColor || '',
      fg: cs.color || '',
      visible,
      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
      locator_hint: hint
    };
  });
}
"""

PAGE_TEXT_JS = r"""() => (document.body && document.body.innerText) ? document.body.innerText : ''"""

L2_STATS_JS = r"""
() => {
  const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';
  const words = bodyText.trim() ? bodyText.trim().split(/\s+/).length : 0;

  const switchLike = Array.from(document.querySelectorAll(
    'input[type="checkbox"], [role="switch"], [role="checkbox"]'
  )).filter(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
  });

  const vendorSelectors = [
    '[class*="vendor" i]', '[id*="vendor" i]',
    '[data-testid*="vendor" i]', '[aria-label*="vendor" i]'
  ];
  const vendorNodes = new Set();
  vendorSelectors.forEach(sel => {
    try {
      document.querySelectorAll(sel).forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) vendorNodes.add(el);
      });
    } catch(e) {}
  });

  const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,[role="heading"]'))
    .map(x => (x.innerText || '').trim())
    .filter(Boolean);

  return {
    words,
    toggle_count: switchLike.length,
    vendor_count: vendorNodes.size,
    headings: headings.slice(0, 100),
    text: bodyText.slice(0, 20000)
  };
}
"""


async def all_frames(page: Page) -> List[Frame]:
    frames = []
    for f in page.frames:
        try:
            _ = f.url
            frames.append(f)
        except Exception:
            pass
    return frames


async def collect_interactives(page: Page) -> List[ElementEvidence]:
    out: List[ElementEvidence] = []
    for frame in await all_frames(page):
        try:
            rows = await frame.evaluate(INTERACTIVE_JS)
        except Exception:
            continue
        for r in rows or []:
            try:
                out.append(
                    ElementEvidence(
                        text=str(r.get("text", "")),
                        tag=str(r.get("tag", "")),
                        role=str(r.get("role", "")),
                        frame_url=str(frame.url or ""),
                        x=float(r.get("x", 0) or 0),
                        y=float(r.get("y", 0) or 0),
                        width=float(r.get("width", 0) or 0),
                        height=float(r.get("height", 0) or 0),
                        font_size=float(r.get("font_size", 0) or 0),
                        font_weight=float(r.get("font_weight", 400) or 400),
                        bg=str(r.get("bg", "")),
                        fg=str(r.get("fg", "")),
                        visible=bool(r.get("visible", False)),
                        disabled=bool(r.get("disabled", False)),
                        locator_hint=str(r.get("locator_hint", "")),
                    )
                )
            except Exception:
                continue
    return [e for e in out if e.visible and not e.disabled and e.text.strip()]


async def page_text_all_frames(page: Page) -> str:
    chunks = []
    for frame in await all_frames(page):
        try:
            t = await frame.evaluate(PAGE_TEXT_JS)
            if t:
                chunks.append(str(t))
        except Exception:
            continue
    return "\n".join(chunks)


def select_action(
    elements: Sequence[ElementEvidence],
    patterns: Sequence[str]
) -> Optional[ElementEvidence]:
    matches = [e for e in elements if text_matches(e.text, patterns)]
    if not matches:
        return None
    # Prefer actual buttons, larger visible controls, then higher/left-most controls.
    def rank(e: ElementEvidence):
        button_bonus = 1 if e.tag in {"button", "input"} or e.role == "button" else 0
        return (button_bonus, e.area, e.font_weight, -e.y, -e.x)
    return sorted(matches, key=rank, reverse=True)[0]


def color_is_nontransparent(value: str) -> bool:
    s = str(value or "").replace(" ", "").lower()
    return bool(s) and s not in {"transparent", "rgba(0,0,0,0)", "rgba(0,0,0,0.0)"}


def prominence_score(
    element: Optional[ElementEvidence],
    peers: Sequence[Optional[ElementEvidence]]
) -> Optional[int]:
    if element is None:
        return None
    valid = [p for p in peers if p is not None]
    if not valid:
        return 2

    median_area = np.median([max(p.area, 1) for p in valid])
    median_font = np.median([max(p.font_size, 1) for p in valid])

    score = 1
    if element.area >= median_area:
        score += 1
    if (
        element.area > median_area * 1.20
        or element.font_size > median_font * 1.10
        or element.font_weight >= 600
        or color_is_nontransparent(element.bg)
    ):
        score = 3
    return int(max(1, min(3, score)))


def size_asymmetry(
    accept: Optional[ElementEvidence], reject: Optional[ElementEvidence]
) -> str:
    if accept is None or reject is None:
        return ""
    a, r = accept.area, reject.area
    if r <= 0 or a <= 0:
        return ""
    if a > r * 1.10:
        return "Larger"
    if r > a * 1.10:
        return "Smaller"
    return "Equal"


async def detect_tcf(page: Page) -> Tuple[int, str]:
    for frame in await all_frames(page):
        try:
            has = await frame.evaluate(
                "() => typeof window.__tcfapi === 'function' || '__tcfapi' in window"
            )
            if has:
                return 1, f"__tcfapi detected in frame: {frame.url}"
        except Exception:
            pass
    text = (await page_text_all_frames(page)).lower()
    if "iab" in text and ("tcf" in text or "transparency and consent framework" in text):
        return 1, "IAB/TCF textual evidence detected"
    return 0, ""


async def detect_cmp(page: Page) -> Tuple[str, str]:
    snippets = []
    for frame in await all_frames(page):
        try:
            html = await frame.content()
            snippets.append(html[:300000].lower())
        except Exception:
            continue
    combined = "\n".join(snippets)
    for vendor, signatures in CMP_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in combined:
                return vendor, f"DOM signature: {sig}"
    return "Unknown/Custom", ""


def detect_sourcepoint_ids(text: str) -> Tuple[str, str, str]:
    msg = ""
    camp = ""
    variants = []
    for pattern in [
        r'["\']?(?:message[_-]?id|messageId)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]+)',
        r'\bsp_message[_-]?id\b[^A-Za-z0-9]+([A-Za-z0-9_-]+)',
    ]:
        m = re.search(pattern, text, flags=re.I)
        if m:
            msg = m.group(1)
            break
    for pattern in [
        r'["\']?(?:campaign[_-]?id|campaignId)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]+)',
        r'\bsp_campaign[_-]?id\b[^A-Za-z0-9]+([A-Za-z0-9_-]+)',
    ]:
        m = re.search(pattern, text, flags=re.I)
        if m:
            camp = m.group(1)
            break
    for p in [r"\bvariant\b.{0,60}", r"\bscenario\b.{0,60}"]:
        variants.extend(re.findall(p, text, flags=re.I)[:3])
    return msg, camp, " | ".join(variants)[:500]


async def frame_locator_from_evidence(
    page: Page, ev: ElementEvidence
):
    for frame in await all_frames(page):
        if str(frame.url or "") == ev.frame_url:
            # First try exact visible text because generated :nth-of-type selectors can be brittle.
            try:
                loc = frame.get_by_text(ev.text, exact=True)
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                pass
            try:
                loc = frame.locator(ev.locator_hint)
                if await loc.count() > 0:
                    return loc.first
            except Exception:
                pass
    return None


async def click_action(page: Page, patterns: Sequence[str]) -> bool:
    elements = await collect_interactives(page)
    ev = select_action(elements, patterns)
    if ev is None:
        return False
    loc = await frame_locator_from_evidence(page, ev)
    if loc is None:
        return False
    try:
        await loc.click(timeout=5_000)
        return True
    except Exception:
        try:
            await loc.click(timeout=5_000, force=True)
            return True
        except Exception:
            return False


async def create_context(
    browser: Browser,
    *,
    locale: str,
    timezone_id: str,
    headless: bool,
) -> BrowserContext:
    # headless is a browser-launch property but retained here in call signature
    # to make the audit configuration explicit.
    return await browser.new_context(
        viewport=DEFAULT_VIEWPORT,
        locale=locale,
        timezone_id=timezone_id,
        java_script_enabled=True,
        bypass_csp=False,
        ignore_https_errors=True,
    )


async def goto_clean(
    browser: Browser,
    url: str,
    *,
    locale: str,
    timezone_id: str,
    headless: bool,
    timeout_ms: int,
    settle_ms: int,
) -> Tuple[BrowserContext, Page, str]:
    context = await create_context(
        browser, locale=locale, timezone_id=timezone_id, headless=headless
    )
    await context.clear_cookies()
    page = await context.new_page()
    final_url = url
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(settle_ms)
        final_url = page.url
    except PlaywrightTimeoutError:
        # Keep the rendered page when navigation timed out after partial load.
        final_url = page.url or url
    return context, page, final_url


async def measure_action_path(
    browser: Browser,
    url: str,
    goal: str,
    *,
    locale: str,
    timezone_id: str,
    headless: bool,
    timeout_ms: int,
    settle_ms: int,
) -> Tuple[Optional[int], bool]:
    """
    Returns (click_count, success).

    Reject reconstruction:
      - direct visible reject -> 1 click
      - manage/settings -> reject -> 2 clicks
      - manage/settings -> reject -> save/confirm -> 3 clicks
    """
    context = None
    try:
        context, page, _ = await goto_clean(
            browser, url, locale=locale, timezone_id=timezone_id,
            headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
        )
        if goal == "accept":
            ok = await click_action(page, ACCEPT_PATTERNS)
            return (1 if ok else None), ok

        if goal == "manage":
            ok = await click_action(page, MANAGE_PATTERNS)
            return (1 if ok else None), ok

        if goal == "reject":
            if await click_action(page, REJECT_PATTERNS):
                return 1, True

            if await click_action(page, MANAGE_PATTERNS):
                await page.wait_for_timeout(700)
                if await click_action(page, REJECT_PATTERNS):
                    await page.wait_for_timeout(400)
                    # Some CMPs require save/confirm after reject-selection.
                    if await click_action(page, SAVE_PATTERNS):
                        return 3, True
                    return 2, True

            return None, False

        raise ValueError(f"Unknown goal: {goal}")
    except Exception:
        return None, False
    finally:
        if context is not None:
            await context.close()


def information_density_score(
    word_count: int,
    toggle_count: int,
    vendor_count: int,
    heading_count: int,
) -> int:
    """
    Deterministic 1--5 interface-density proxy for newly acquired audits.

    The historical manuscript dataset contains an independently coded
    L2_Information_Density_Score_1to5. This rule makes new acquisition runs
    executable and reproducible; it must not be represented as the historical
    coding rule unless independently verified.

    The score combines textual amount and control density rather than word count
    alone. Threshold 4 remains the final high-information-density cutoff.
    """
    burden = 0
    if word_count >= 400:
        burden += 1
    if word_count >= 900:
        burden += 1
    if word_count >= 1500:
        burden += 1
    if toggle_count + vendor_count >= 20:
        burden += 1
    if heading_count >= 12:
        burden += 1
    return int(max(1, min(5, 1 + burden)))


def germane_support_score(text: str, headings: Sequence[str]) -> int:
    """
    Reproducible structural support score for newly acquired audits.

    This is a transparent automated approximation of explanatory support.
    It is not a psychometric measure and should not replace archived human
    annotations where those annotations are the manuscript source.
    """
    low = (text or "").lower()
    keyword_hits = sum(1 for k in EXPLANATION_KEYWORDS if k in low)
    heading_hits = sum(
        1 for h in headings
        if any(k in h.lower() for k in ("purpose", "vendor", "privacy", "cookie", "partner"))
    )
    word_count = len(re.findall(r"\b\w+\b", text or ""))
    score = 1
    if keyword_hits >= 2:
        score += 1
    if keyword_hits >= 5:
        score += 1
    if heading_hits >= 2:
        score += 1
    if word_count >= 500:
        score += 1
    return int(max(1, min(5, score)))


async def collect_l2(
    page: Page,
) -> Dict[str, Any]:
    aggregate = {
        "words": 0,
        "toggle_count": 0,
        "vendor_count": 0,
        "headings": [],
        "text": "",
    }
    for frame in await all_frames(page):
        try:
            d = await frame.evaluate(L2_STATS_JS)
        except Exception:
            continue
        aggregate["words"] += int(d.get("words", 0) or 0)
        aggregate["toggle_count"] += int(d.get("toggle_count", 0) or 0)
        aggregate["vendor_count"] += int(d.get("vendor_count", 0) or 0)
        aggregate["headings"].extend(d.get("headings", []) or [])
        if d.get("text"):
            aggregate["text"] += "\n" + str(d["text"])
    return aggregate


def banner_type(
    accept: Optional[ElementEvidence],
    reject: Optional[ElementEvidence],
    manage: Optional[ElementEvidence],
) -> str:
    present = [
        name for name, obj in
        [("Accept", accept), ("Reject", reject), ("Manage", manage)]
        if obj is not None
    ]
    if len(present) >= 3:
        return "Multi-option"
    if accept is not None and reject is None and manage is None:
        return "Accept-only"
    if accept is not None and manage is not None and reject is None:
        return "Accept + Manage"
    if accept is not None and reject is not None:
        return "Accept + Reject"
    return "Other/Unknown"


async def check_reprompt_after_reject(
    browser: Browser,
    url: str,
    *,
    locale: str,
    timezone_id: str,
    headless: bool,
    timeout_ms: int,
    settle_ms: int,
) -> Tuple[Optional[int], Optional[int]]:
    context = None
    try:
        context, page, _ = await goto_clean(
            browser, url, locale=locale, timezone_id=timezone_id,
            headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
        )
        rejected = False
        if await click_action(page, REJECT_PATTERNS):
            rejected = True
        elif await click_action(page, MANAGE_PATTERNS):
            await page.wait_for_timeout(700)
            if await click_action(page, REJECT_PATTERNS):
                rejected = True
                await page.wait_for_timeout(300)
                await click_action(page, SAVE_PATTERNS)

        if not rejected:
            return None, None

        observed = 0
        for _ in range(2):
            await page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(settle_ms)
            els = await collect_interactives(page)
            a = select_action(els, ACCEPT_PATTERNS)
            r = select_action(els, REJECT_PATTERNS)
            m = select_action(els, MANAGE_PATTERNS)
            txt = (await page_text_all_frames(page)).lower()
            banner_again = (
                any(k in txt for k in BANNER_KEYWORDS) and
                any(x is not None for x in (a, r, m))
            )
            observed += int(bool(banner_again))
        return int(observed > 0), observed
    except Exception:
        return None, None
    finally:
        if context is not None:
            await context.close()


async def audit_one(
    browser: Browser,
    url: str,
    idx: int,
    *,
    run_id: str,
    screenshots_dir: Path,
    evidence_dir: Path,
    locale: str,
    timezone_id: str,
    market: str,
    headless: bool,
    timeout_ms: int,
    settle_ms: int,
    test_reprompt: bool,
) -> Dict[str, Any]:
    rec = {c: "" for c in AUDIT_COLUMNS}
    rec.update(
        {
            "Website_ID": stable_site_id(url, idx),
            "Domain": domain_of(url),
            "URL_Accessed": url,
            "Audit_Status": "Started",
            "Last_Error": "",
            "Retry_Count": 0,
            "Audit_Level": "L1",
            "Run_ID": run_id,
            "Access_Date_UTC": utc_now_iso(),
            "Country_or_Market_Observed": market,
            "Access_Locale": locale,
            "Browser": "Chromium/Playwright",
            "Headless_Audit": int(headless),
        }
    )

    context = None
    evidence: Dict[str, Any] = {
        "version": VERSION,
        "url_requested": url,
        "website_id": rec["Website_ID"],
        "run_id": run_id,
        "timestamp_utc": rec["Access_Date_UTC"],
        "configuration": {
            "locale": locale,
            "timezone_id": timezone_id,
            "viewport": DEFAULT_VIEWPORT,
            "headless": headless,
            "timeout_ms": timeout_ms,
            "settle_ms": settle_ms,
        },
    }

    try:
        context, page, final_url = await goto_clean(
            browser, url, locale=locale, timezone_id=timezone_id,
            headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
        )
        rec["URL_Accessed"] = final_url
        rec["Domain"] = domain_of(final_url) or domain_of(url)

        text = await page_text_all_frames(page)
        elements = await collect_interactives(page)
        accept = select_action(elements, ACCEPT_PATTERNS)
        reject = select_action(elements, REJECT_PATTERNS)
        manage = select_action(elements, MANAGE_PATTERNS)

        cookie_text = any(k in text.lower() for k in BANNER_KEYWORDS)
        banner_present = int(cookie_text and any(x is not None for x in (accept, reject, manage)))
        rec["Cookie_Banner_Present"] = banner_present
        rec["Banner_Type"] = banner_type(accept, reject, manage) if banner_present else "None"
        rec["L1_Accept_All_Present"] = int(accept is not None)
        rec["L1_Reject_All_Present"] = int(reject is not None)
        rec["L1_Manage_Preferences_Present"] = int(manage is not None)

        peers = [accept, reject, manage]
        a_prom = prominence_score(accept, peers)
        r_prom = prominence_score(reject, peers)
        rec["AE_Accept_Button_Prominence_1to3"] = a_prom if a_prom is not None else ""
        rec["AE_Reject_Button_Prominence_1to3"] = r_prom if r_prom is not None else ""
        rec["AE_Size_Asymmetry_LargerEqualSmaller"] = size_asymmetry(accept, reject)
        rec["AE_Primary_Action_Is_Accept"] = int(
            accept is not None and (
                reject is None or
                (a_prom or 0) >= (r_prom or 0)
            )
        )

        cmp_vendor, cmp_evidence = await detect_cmp(page)
        rec["CMP_Vendor"] = cmp_vendor
        rec["CMP_Evidence"] = cmp_evidence

        tcf, tcf_evidence = await detect_tcf(page)
        rec["IAB_TCF_Mentioned"] = tcf
        rec["TCF_Evidence"] = tcf_evidence

        # Best-effort L1 evidence quote, limited for repository redistribution.
        lines = [" ".join(x.split()) for x in text.splitlines() if x.strip()]
        relevant = [x for x in lines if any(k in x.lower() for k in BANNER_KEYWORDS)]
        rec["L1_Evidence_Quote"] = (relevant[0] if relevant else "")[:500]

        if banner_present:
            shot_name = f"{rec['Website_ID']}_L1.png"
            shot_path = screenshots_dir / shot_name
            try:
                await page.screenshot(path=str(shot_path), full_page=False)
                rec["L1_Screenshot_Ref"] = str(shot_path.as_posix())
            except Exception:
                pass

        # Inspect page source for Sourcepoint identifiers.
        html_sample = ""
        for frame in await all_frames(page):
            try:
                html_sample += "\n" + (await frame.content())[:250000]
            except Exception:
                pass
        sp_msg, sp_camp, sp_variant = detect_sourcepoint_ids(html_sample)
        rec["SP_Message_ID"] = sp_msg
        rec["SP_Campaign_ID"] = sp_camp
        rec["SP_Variant_Evidence"] = sp_variant

        evidence["l1"] = {
            "banner_present": banner_present,
            "accept": accept.__dict__ if accept else None,
            "reject": reject.__dict__ if reject else None,
            "manage": manage.__dict__ if manage else None,
            "cmp_vendor": cmp_vendor,
            "tcf": tcf,
        }

        await context.close()
        context = None

        # Reconstruct each action from an independent clean browser context.
        if banner_present:
            accept_count, _ = await measure_action_path(
                browser, url, "accept", locale=locale, timezone_id=timezone_id,
                headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
            )
            reject_count, reject_success = await measure_action_path(
                browser, url, "reject", locale=locale, timezone_id=timezone_id,
                headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
            )
            manage_count, manage_success = await measure_action_path(
                browser, url, "manage", locale=locale, timezone_id=timezone_id,
                headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
            )

            rec["Accept_Click_Count"] = accept_count if accept_count is not None else ""
            rec["Reject_Click_Count"] = reject_count if reject_count is not None else ""
            rec["Manage_Click_Count"] = manage_count if manage_count is not None else ""

            if accept_count is not None and reject_count is not None:
                rec["EE_Click_Asymmetry_RejectMinusAccept"] = reject_count - accept_count
            else:
                rec["EE_Click_Asymmetry_RejectMinusAccept"] = ""

            rec["EE_Hidden_Reject_Path"] = int(
                reject is None and bool(reject_success) and bool(manage_success)
            )

            # Layer-2 reconstruction in a fresh context.
            l2_context, l2_page, _ = await goto_clean(
                browser, url, locale=locale, timezone_id=timezone_id,
                headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
            )
            try:
                l2_open = await click_action(l2_page, MANAGE_PATTERNS)
                if l2_open:
                    await l2_page.wait_for_timeout(800)
                    l2 = await collect_l2(l2_page)
                    rec["L2_Available"] = 1
                    rec["Consent_Layer_Depth"] = 2
                    rec["Audit_Level"] = "L2"
                    rec["L2_Toggle_Count"] = int(l2["toggle_count"])
                    rec["L2_Vendor_Count"] = int(l2["vendor_count"])
                    rec["L2_Text_Word_Count"] = int(l2["words"])
                    rec["CL_Toggle_Vendor_Complexity_Index"] = (
                        int(l2["toggle_count"]) + int(l2["vendor_count"])
                    )

                    info_score = information_density_score(
                        int(l2["words"]),
                        int(l2["toggle_count"]),
                        int(l2["vendor_count"]),
                        len(l2["headings"]),
                    )
                    germane_score = germane_support_score(
                        l2["text"], l2["headings"]
                    )
                    rec["L2_Information_Density_Score_1to5"] = info_score
                    rec["L2_Germane_Support_Score_1to5"] = germane_score
                    rec["CL_Germane_Suppression_Indicators"] = int(germane_score <= 2)

                    l2_lines = [
                        " ".join(x.split()) for x in l2["text"].splitlines() if x.strip()
                    ]
                    rec["L2_Evidence_Quote"] = (
                        " | ".join(l2_lines[:3])[:700] if l2_lines else ""
                    )

                    shot_name = f"{rec['Website_ID']}_L2.png"
                    shot_path = screenshots_dir / shot_name
                    try:
                        await l2_page.screenshot(path=str(shot_path), full_page=False)
                        rec["L2_Screenshot_Ref"] = str(shot_path.as_posix())
                    except Exception:
                        pass

                    # Best-effort OneTrust counts.
                    if cmp_vendor == "OneTrust":
                        rec["OT_Purpose_Count"] = int(l2["toggle_count"])
                        rec["OT_Vendor_Count"] = int(l2["vendor_count"])

                    evidence["l2"] = {
                        "toggle_count": int(l2["toggle_count"]),
                        "vendor_count": int(l2["vendor_count"]),
                        "word_count": int(l2["words"]),
                        "heading_count": len(l2["headings"]),
                        "information_density_score": info_score,
                        "germane_support_score": germane_score,
                        "complexity_index": int(l2["toggle_count"]) + int(l2["vendor_count"]),
                    }
                else:
                    rec["L2_Available"] = 0
                    rec["Consent_Layer_Depth"] = 1
            finally:
                await l2_context.close()

            if test_reprompt and reject_success:
                aa, freq = await check_reprompt_after_reject(
                    browser, url, locale=locale, timezone_id=timezone_id,
                    headless=headless, timeout_ms=timeout_ms, settle_ms=settle_ms
                )
                rec["AA_RePrompting_After_Reject"] = aa if aa is not None else ""
                rec["AA_RePrompt_Frequency_Observed"] = freq if freq is not None else ""
        else:
            rec["L2_Available"] = 0
            rec["Consent_Layer_Depth"] = 0

        rec["Audit_Status"] = "Completed"

    except Exception as exc:
        rec["Audit_Status"] = "Error"
        rec["Last_Error"] = f"{type(exc).__name__}: {exc}"[:1000]
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass

        evidence["final_record"] = {
            k: v for k, v in rec.items()
            if k not in {"L1_Evidence_Quote", "L2_Evidence_Quote"}
        }
        evidence_path = evidence_dir / f"{rec['Website_ID']}.json"
        try:
            evidence_path.write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            rec["Evidence_JSON_Ref"] = str(evidence_path.as_posix())
        except Exception:
            pass

    return rec


async def run_audit(args: argparse.Namespace) -> Path:
    if async_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && "
            "playwright install chromium"
        )

    input_path = Path(args.input)
    output_path = Path(args.output)
    screenshots_dir = Path(args.screenshots)
    evidence_dir = Path(args.evidence)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    targets = load_targets(input_path)
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        raise RuntimeError("No valid targets found.")

    run_id = args.run_id or f"ACLDP-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    print(f"ACL-DP {VERSION}")
    print(f"Run ID: {run_id}")
    print(f"Targets: {len(targets)}")

    rows: List[Dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)
        try:
            for idx, url in enumerate(targets, start=1):
                print(f"[{idx}/{len(targets)}] {url}")
                rec = await audit_one(
                    browser,
                    url,
                    idx,
                    run_id=run_id,
                    screenshots_dir=screenshots_dir,
                    evidence_dir=evidence_dir,
                    locale=args.locale,
                    timezone_id=args.timezone,
                    market=args.market,
                    headless=args.headless,
                    timeout_ms=args.timeout_ms,
                    settle_ms=args.settle_ms,
                    test_reprompt=args.test_reprompt,
                )
                rows.append(rec)
                # Incremental checkpoint after every site.
                pd.DataFrame(rows, columns=AUDIT_COLUMNS).to_csv(
                    output_path, index=False
                )
        finally:
            await browser.close()

    print(f"Audit dataset written to: {output_path}")
    return output_path


# ---------------------------------------------------------------------
# Final scoring and statistical reproduction
# ---------------------------------------------------------------------
def derive_scores(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    col_banner = find_col(df.columns, ["Cookie_Banner_Present"])
    col_l2 = find_col(df.columns, ["L2_Available", "Layer_2_Available"])
    col_accept_click = find_col(df.columns, ["Accept_Click_Count"])
    col_reject_click = find_col(df.columns, ["Reject_Click_Count"])
    col_hidden_reject = find_col(df.columns, ["EE_Hidden_Reject_Path"])
    col_primary_accept = find_col(df.columns, ["AE_Primary_Action_Is_Accept"])
    col_accept_prom = find_col(
        df.columns,
        ["AE_Accept_Button_Prominence_1to3", "AE_Accept_Button_Prominence"],
    )
    col_reject_prom = find_col(
        df.columns,
        ["AE_Reject_Button_Prominence_1to3", "AE_Reject_Button_Prominence"],
    )
    col_complexity = find_col(
        df.columns,
        ["CL_Toggle_Vendor_Complexity_Index", "complexity_index"],
    )
    col_info_density = find_col(
        df.columns,
        ["L2_Information_Density_Score_1to5", "L2_Information_Density_Score"],
    )
    col_toggle_count = find_col(df.columns, ["L2_Toggle_Count", "toggle_count"])
    col_germane = find_col(
        df.columns,
        ["CL_Germane_Suppression_Indicators", "germane_suppression_indicators"],
    )

    if col_banner:
        banner_flag = to_binary_yes_no(df[col_banner])
        df_main = df[banner_flag == 1].copy()
    else:
        inferred = pd.Series(False, index=df.index)
        if col_primary_accept:
            inferred |= to_binary_yes_no(df[col_primary_accept]).fillna(0).eq(1)
        if col_accept_click:
            inferred |= to_numeric(df[col_accept_click]).notna()
        df_main = df[inferred].copy()

    if col_l2:
        l2_flag = to_binary_yes_no(df_main[col_l2])
        l2_idx = df_main.index[l2_flag == 1]
    else:
        inferred = pd.Series(False, index=df_main.index)
        if col_info_density:
            inferred |= to_numeric(df_main[col_info_density]).notna()
        if col_toggle_count:
            inferred |= to_numeric(df_main[col_toggle_count]).notna()
        if col_complexity:
            inferred |= to_numeric(df_main[col_complexity]).notna()
        l2_idx = df_main.index[inferred]

    accept_click = (
        to_numeric(df_main[col_accept_click])
        if col_accept_click else pd.Series(np.nan, index=df_main.index)
    )
    reject_click = (
        to_numeric(df_main[col_reject_click])
        if col_reject_click else pd.Series(np.nan, index=df_main.index)
    )

    effort_valid = accept_click.notna() & reject_click.notna()
    df_main["EFFORT_VALID"] = effort_valid.astype(int)
    df_main["MECH_EE_ClickAsymmetry"] = np.where(
        effort_valid & (reject_click > accept_click), 1, 0
    )
    if col_hidden_reject:
        df_main["MECH_EE_HiddenReject"] = (
            to_binary_yes_no(df_main[col_hidden_reject]).fillna(0).astype(int)
        )
    else:
        df_main["MECH_EE_HiddenReject"] = 0

    if col_primary_accept:
        df_main["MECH_AE_PrimaryAccept"] = (
            to_binary_yes_no(df_main[col_primary_accept]).fillna(0).astype(int)
        )
    else:
        df_main["MECH_AE_PrimaryAccept"] = 0

    if col_accept_prom and col_reject_prom:
        ap = to_numeric(df_main[col_accept_prom])
        rp = to_numeric(df_main[col_reject_prom])
        df_main["MECH_AE_ProminenceAsymmetry"] = np.where(
            ap.notna() & rp.notna() & (ap > rp), 1, 0
        )
    else:
        df_main["MECH_AE_ProminenceAsymmetry"] = 0

    for c in [
        "MECH_CL_HighComplexity",
        "MECH_CL_HighInfoDensity",
        "MECH_CL_HighToggleVolume",
        "MECH_CL_GermaneSuppression",
    ]:
        df_main[c] = 0

    if len(l2_idx) > 0:
        if col_complexity:
            v = to_numeric(df_main.loc[l2_idx, col_complexity])
            df_main.loc[l2_idx, "MECH_CL_HighComplexity"] = (
                v >= BASE_COMPLEXITY_THRESHOLD
            ).astype(int)

        if col_info_density:
            v = to_numeric(df_main.loc[l2_idx, col_info_density])
            df_main.loc[l2_idx, "MECH_CL_HighInfoDensity"] = (
                v >= BASE_INFO_DENSITY_THRESHOLD
            ).astype(int)

        if col_toggle_count:
            v = to_numeric(df_main.loc[l2_idx, col_toggle_count])
            # Historical baseline toggle-volume threshold used in sensitivity
            # analysis; this indicator is NOT part of the final CL score.
            df_main.loc[l2_idx, "MECH_CL_HighToggleVolume"] = (v >= 13).astype(int)

        if col_germane:
            v = to_binary_yes_no(df_main.loc[l2_idx, col_germane])
            df_main.loc[l2_idx, "MECH_CL_GermaneSuppression"] = (
                v.fillna(0).astype(int)
            )

    df_main["EFFORT_SCORE"] = (
        df_main["MECH_EE_ClickAsymmetry"] +
        df_main["MECH_EE_HiddenReject"]
    )
    df_main["ATTENTION_SCORE"] = (
        df_main["MECH_AE_PrimaryAccept"] +
        df_main["MECH_AE_ProminenceAsymmetry"]
    )
    df_main["COGNITIVE_LOAD_SCORE"] = (
        df_main["MECH_CL_HighComplexity"] +
        df_main["MECH_CL_HighInfoDensity"] +
        df_main["MECH_CL_GermaneSuppression"]
    )
    df_main["ACLDP_TOTAL_SCORE"] = (
        df_main["EFFORT_SCORE"] +
        df_main["ATTENTION_SCORE"] +
        df_main["COGNITIVE_LOAD_SCORE"]
    )

    meta = {
        "n_input": int(len(df)),
        "n_observable_interfaces": int(len(df_main)),
        "n_effort_valid": int(df_main["EFFORT_VALID"].sum()),
        "n_layer2": int(len(l2_idx)),
        "score_definition": (
            "ACLDP_TOTAL_SCORE = EFFORT_SCORE + ATTENTION_SCORE + "
            "COGNITIVE_LOAD_SCORE"
        ),
        "score_range": "0-7",
        "aa_included_in_total": False,
        "toggle_volume_included_in_cl_score": False,
    }
    return df_main, meta


def descriptive_summary(df_main: pd.DataFrame) -> pd.DataFrame:
    n = len(df_main)
    effort = df_main[df_main["EFFORT_VALID"] == 1]
    rows = [
        {
            "Measure": "Observable consent interfaces",
            "Numerator": n,
            "Denominator": n,
            "Percent": 100.0 if n else np.nan,
        },
        {
            "Measure": "AE primary-action bias toward acceptance",
            "Numerator": int(df_main["MECH_AE_PrimaryAccept"].sum()),
            "Denominator": n,
            "Percent": 100 * df_main["MECH_AE_PrimaryAccept"].mean() if n else np.nan,
        },
        {
            "Measure": "EE click asymmetry",
            "Numerator": int(effort["MECH_EE_ClickAsymmetry"].sum()),
            "Denominator": len(effort),
            "Percent": 100 * effort["MECH_EE_ClickAsymmetry"].mean()
            if len(effort) else np.nan,
        },
        {
            "Measure": "EE hidden reject path",
            "Numerator": int(effort["MECH_EE_HiddenReject"].sum()),
            "Denominator": len(effort),
            "Percent": 100 * effort["MECH_EE_HiddenReject"].mean()
            if len(effort) else np.nan,
        },
        {
            "Measure": "Layer-2 interfaces",
            "Numerator": int(
                (df_main["COGNITIVE_LOAD_SCORE"].notna()).sum()
            ),
            "Denominator": n,
            # This row is replaced below when L2_Available exists in scored data.
            "Percent": np.nan,
        },
    ]
    return pd.DataFrame(rows)


def pairwise_spearman(df_main: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "EFFORT_SCORE",
        "ATTENTION_SCORE",
        "COGNITIVE_LOAD_SCORE",
        "ACLDP_TOTAL_SCORE",
    ]
    matrix = df_main[cols].corr(method="spearman")
    return matrix


def threshold_sensitivity(
    df_main: pd.DataFrame,
    original_columns: Sequence[str],
) -> pd.DataFrame:
    complexity_col = find_col(
        original_columns,
        ["CL_Toggle_Vendor_Complexity_Index", "complexity_index"],
    )
    info_col = find_col(
        original_columns,
        ["L2_Information_Density_Score_1to5", "L2_Information_Density_Score"],
    )
    toggle_col = find_col(original_columns, ["L2_Toggle_Count", "toggle_count"])
    l2_col = find_col(original_columns, ["L2_Available", "Layer_2_Available"])

    if complexity_col is None or info_col is None:
        return pd.DataFrame(
            [{"note": "Sensitivity analysis unavailable: required CL source columns missing."}]
        )

    if l2_col:
        l2_mask = to_binary_yes_no(df_main[l2_col]).fillna(0).eq(1)
    else:
        l2_mask = (
            to_numeric(df_main[complexity_col]).notna() |
            to_numeric(df_main[info_col]).notna()
        )

    baseline = df_main["ACLDP_TOTAL_SCORE"].astype(float)
    results = []

    for ct in COMPLEXITY_SENSITIVITY_THRESHOLDS:
        for it in INFO_DENSITY_SENSITIVITY_THRESHOLDS:
            # Toggle threshold is reported for sensitivity completeness but does
            # not change the FINAL total score because HighToggleVolume is not
            # included in COGNITIVE_LOAD_SCORE.
            for tt in TOGGLE_SENSITIVITY_THRESHOLDS:
                alt_complex = pd.Series(0, index=df_main.index, dtype=int)
                alt_info = pd.Series(0, index=df_main.index, dtype=int)
                alt_complex.loc[l2_mask] = (
                    to_numeric(df_main.loc[l2_mask, complexity_col]) >= ct
                ).astype(int)
                alt_info.loc[l2_mask] = (
                    to_numeric(df_main.loc[l2_mask, info_col]) >= it
                ).astype(int)

                alt_cl = (
                    alt_complex +
                    alt_info +
                    df_main["MECH_CL_GermaneSuppression"].astype(int)
                )
                alt_total = (
                    df_main["EFFORT_SCORE"].astype(int) +
                    df_main["ATTENTION_SCORE"].astype(int) +
                    alt_cl
                )

                valid = baseline.notna() & alt_total.notna()
                if valid.sum() >= 2:
                    rho, _ = spearmanr(baseline[valid], alt_total[valid])
                else:
                    rho = np.nan
                exact = (
                    float((baseline[valid] == alt_total[valid]).mean())
                    if valid.any() else np.nan
                )
                mad = (
                    float((baseline[valid] - alt_total[valid]).abs().mean())
                    if valid.any() else np.nan
                )
                results.append(
                    {
                        "Complexity_Threshold": ct,
                        "Information_Density_Threshold": it,
                        "Toggle_Volume_Threshold_Supplementary": tt,
                        "N": int(valid.sum()),
                        "Spearman_rho": rho,
                        "Exact_Agreement": exact,
                        "MAD": mad,
                    }
                )
    return pd.DataFrame(results)


def run_analysis(input_path: Path, results_dir: Path) -> Dict[str, Path]:
    results_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(input_path)
    df.columns = [str(c).strip() for c in df.columns]

    scored, meta = derive_scores(df)

    scored_path = results_dir / "acldp_scored_interfaces.csv"
    scored.to_csv(scored_path, index=False)

    # Sample-aware descriptive results.
    summary_rows = []
    n76 = len(scored)
    effort = scored[scored["EFFORT_VALID"] == 1]

    def add(name: str, num: int, den: int):
        summary_rows.append(
            {
                "Measure": name,
                "Numerator": int(num),
                "Denominator": int(den),
                "Percent": (100.0 * num / den) if den else np.nan,
            }
        )

    add(
        "AE primary-action bias toward acceptance",
        int(scored["MECH_AE_PrimaryAccept"].sum()),
        n76,
    )
    add(
        "EE click asymmetry",
        int(effort["MECH_EE_ClickAsymmetry"].sum()),
        len(effort),
    )
    add(
        "EE hidden reject path",
        int(effort["MECH_EE_HiddenReject"].sum()),
        len(effort),
    )

    l2_col = find_col(scored.columns, ["L2_Available", "Layer_2_Available"])
    if l2_col:
        l2 = to_binary_yes_no(scored[l2_col]).fillna(0).astype(int)
        add("Layer-2 panels available", int(l2.sum()), n76)

    summary = pd.DataFrame(summary_rows)
    summary_path = results_dir / "descriptive_summary.csv"
    summary.to_csv(summary_path, index=False)

    corr = pairwise_spearman(scored)
    corr_path = results_dir / "spearman_correlations.csv"
    corr.to_csv(corr_path)

    sensitivity = threshold_sensitivity(scored, scored.columns)
    sensitivity_path = results_dir / "threshold_sensitivity.csv"
    sensitivity.to_csv(sensitivity_path, index=False)

    metadata_path = results_dir / "analysis_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                **meta,
                "input_file": str(input_path),
                "generated_utc": utc_now_iso(),
                "version": VERSION,
                "final_scoring": {
                    "EFFORT_SCORE": (
                        "MECH_EE_ClickAsymmetry + MECH_EE_HiddenReject"
                    ),
                    "ATTENTION_SCORE": (
                        "MECH_AE_PrimaryAccept + MECH_AE_ProminenceAsymmetry"
                    ),
                    "COGNITIVE_LOAD_SCORE": (
                        "MECH_CL_HighComplexity + MECH_CL_HighInfoDensity + "
                        "MECH_CL_GermaneSuppression"
                    ),
                    "ACLDP_TOTAL_SCORE": (
                        "EFFORT_SCORE + ATTENTION_SCORE + COGNITIVE_LOAD_SCORE"
                    ),
                    "range": [0, 7],
                    "AA_excluded": True,
                    "HighToggleVolume_excluded_from_final_CL": True,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\nAnalysis complete")
    print(json.dumps(meta, indent=2))
    print(f"Scored data: {scored_path}")
    print(f"Descriptive summary: {summary_path}")
    print(f"Spearman correlations: {corr_path}")
    print(f"Threshold sensitivity: {sensitivity_path}")
    print(f"Metadata: {metadata_path}")

    return {
        "scored": scored_path,
        "summary": summary_path,
        "correlations": corr_path,
        "sensitivity": sensitivity_path,
        "metadata": metadata_path,
    }


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def add_common_audit_args(p: argparse.ArgumentParser):
    p.add_argument("--input", required=True, help="TXT/CSV containing domains or URLs")
    p.add_argument(
        "--output",
        default="dataset/acldp_audit_raw.csv",
        help="Raw audit CSV output",
    )
    p.add_argument(
        "--screenshots",
        default="artifacts/screenshots",
        help="Screenshot output directory",
    )
    p.add_argument(
        "--evidence",
        default="artifacts/evidence",
        help="Structured JSON evidence directory",
    )
    p.add_argument("--locale", default=DEFAULT_LOCALE)
    p.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    p.add_argument(
        "--market",
        default="Saudi Arabia",
        help="Descriptive market/vantage-point label",
    )
    p.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument("--timeout-ms", type=int, default=DEFAULT_TIMEOUT_MS)
    p.add_argument("--settle-ms", type=int, default=DEFAULT_SETTLE_MS)
    p.add_argument("--run-id", default="")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument(
        "--test-reprompt",
        action="store_true",
        help="Optional AA re-prompting check after rejection",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ACL-DP executable computational audit and analysis pipeline"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Acquire consent-interface audit evidence")
    add_common_audit_args(audit)

    analyze = sub.add_parser("analyze", help="Score and analyze an existing audit dataset")
    analyze.add_argument("--input", required=True, help="Audit/anonymized CSV")
    analyze.add_argument("--results", default="results")

    both = sub.add_parser("all", help="Run acquisition followed by scoring/analysis")
    add_common_audit_args(both)
    both.add_argument("--results", default="results")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "audit":
            asyncio.run(run_audit(args))
        elif args.command == "analyze":
            run_analysis(Path(args.input), Path(args.results))
        elif args.command == "all":
            audit_path = asyncio.run(run_audit(args))
            run_analysis(audit_path, Path(args.results))
        else:
            parser.error("Unknown command")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
    for cand in candidates:\
        if cand.lower() in df_map:\
            return df_map[cand.lower()]\
\
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())\
    norm_map = \{norm(c): c for c in df_cols\}\
    for cand in candidates:\
        if norm(cand) in norm_map:\
            return norm_map[norm(cand)]\
    return None\
\
\
def to_numeric(series):\
    return pd.to_numeric(series, errors="coerce")\
\
\
def to_binary_yes_no(series):\
    if series is None:\
        return pd.Series(dtype=float)\
\
    s = series.astype(str).str.strip().str.lower()\
    out = pd.Series(np.nan, index=series.index, dtype=float)\
\
    yes_vals = \{"1", "yes", "y", "true", "present", "available"\}\
    no_vals = \{"0", "no", "n", "false", "absent", "not available"\}\
\
    out[s.isin(yes_vals)] = 1\
    out[s.isin(no_vals)] = 0\
\
    num = pd.to_numeric(series, errors="coerce")\
    out[num == 1] = 1\
    out[num == 0] = 0\
    return out\
\
\
def fmt_num(x, nd=3):\
    if pd.isna(x):\
        return "NA"\
    return f"\{x:.\{nd\}f\}"\
\
\
def fmt_p(x):\
    if pd.isna(x):\
        return "NA"\
    if x < 0.001:\
        return "<0.001"\
    return f"\{x:.3f\}"\
\
\
def fmt_ci(lo, hi, nd=3):\
    if pd.isna(lo) or pd.isna(hi):\
        return "NA"\
    return f"[\{lo:.\{nd\}f\}, \{hi:.\{nd\}f\}]"\
\
\
def latex_escape(s):\
    return str(s).replace("_", r"\\_")\
\
\
# =========================================================\
# 3. Detect columns\
# =========================================================\
col_banner = find_col(df.columns, [\
    "Cookie_Banner_Present", "cookie_banner_present"\
])\
col_l2 = find_col(df.columns, [\
    "L2_Available", "l2_available", "Layer_2_Available"\
])\
\
col_accept_click = find_col(df.columns, [\
    "Accept_Click_Count", "accept_click_count"\
])\
col_reject_click = find_col(df.columns, [\
    "Reject_Click_Count", "reject_click_count"\
])\
col_hidden_reject = find_col(df.columns, [\
    "EE_Hidden_Reject_Path", "hidden_reject_path"\
])\
\
col_primary_accept = find_col(df.columns, [\
    "AE_Primary_Action_Is_Accept", "primary_action_is_accept"\
])\
col_accept_prom = find_col(df.columns, [\
    "AE_Accept_Button_Prominence_1to3", "AE_Accept_Button_Prominence", "accept_button_prominence"\
])\
col_reject_prom = find_col(df.columns, [\
    "AE_Reject_Button_Prominence_1to3", "AE_Reject_Button_Prominence", "reject_button_prominence"\
])\
\
col_complexity = find_col(df.columns, [\
    "CL_Toggle_Vendor_Complexity_Index", "complexity_index"\
])\
col_info_density = find_col(df.columns, [\
    "L2_Information_Density_Score_1to5", "L2_Information_Density_Score", "information_density_score"\
])\
col_toggle_count = find_col(df.columns, [\
    "L2_Toggle_Count", "toggle_count"\
])\
col_germane = find_col(df.columns, [\
    "CL_Germane_Suppression_Indicators", "germane_suppression_indicators"\
])\
\
col_cmp = find_col(df.columns, ["CMP_Vendor", "cmp_vendor", "CMP_Group"])\
col_sector = find_col(df.columns, ["Sector_Group", "sector_group"])\
\
print("\\nDetected columns:")\
for k, v in \{\
    "Cookie_Banner_Present": col_banner,\
    "L2_Available": col_l2,\
    "Accept_Click_Count": col_accept_click,\
    "Reject_Click_Count": col_reject_click,\
    "EE_Hidden_Reject_Path": col_hidden_reject,\
    "AE_Primary_Action_Is_Accept": col_primary_accept,\
    "AE_Accept_Button_Prominence": col_accept_prom,\
    "AE_Reject_Button_Prominence": col_reject_prom,\
    "CL_Toggle_Vendor_Complexity_Index": col_complexity,\
    "L2_Information_Density_Score": col_info_density,\
    "L2_Toggle_Count": col_toggle_count,\
    "CL_Germane_Suppression_Indicators": col_germane,\
    "CMP_Vendor": col_cmp,\
    "Sector_Group": col_sector,\
\}.items():\
    print(f"\{k\}: \{v\}")\
\
\
# =========================================================\
# 4. Restrict to the correct analytical subset\
#    Stage 1/2/3 main sample = observable consent interfaces\
# =========================================================\
if col_banner:\
    banner_flag = to_binary_yes_no(df[col_banner])\
    df_main = df[banner_flag == 1].copy()\
else:\
    # fallback: infer banner sample from presence of primary action / accept button / click count\
    inferred_banner = pd.Series(False, index=df.index)\
    if col_primary_accept:\
        inferred_banner |= to_binary_yes_no(df[col_primary_accept]).fillna(0).astype(int).eq(1)\
    if col_accept_click:\
        inferred_banner |= to_numeric(df[col_accept_click]).notna()\
    df_main = df[inferred_banner].copy()\
\
print("\\nMain analytical subset shape:", df_main.shape)\
\
# Layer-2 nested subset\
if col_l2:\
    l2_flag = to_binary_yes_no(df_main[col_l2])\
    df_l2 = df_main[l2_flag == 1].copy()\
else:\
    # infer from info density / toggle / complexity availability\
    inferred_l2 = pd.Series(False, index=df_main.index)\
    if col_info_density:\
        inferred_l2 |= to_numeric(df_main[col_info_density]).notna()\
    if col_toggle_count:\
        inferred_l2 |= to_numeric(df_main[col_toggle_count]).notna()\
    if col_complexity:\
        inferred_l2 |= to_numeric(df_main[col_complexity]).notna()\
    df_l2 = df_main[inferred_l2].copy()\
\
print("Layer-2 subset shape:", df_l2.shape)\
\
\
# =========================================================\
# 5. Build mechanism indicators on main sample\
# =========================================================\
accept_click = to_numeric(df_main[col_accept_click]) if col_accept_click else pd.Series(np.nan, index=df_main.index)\
reject_click = to_numeric(df_main[col_reject_click]) if col_reject_click else pd.Series(np.nan, index=df_main.index)\
\
# valid effort subset = interfaces with observable rejection pathway\
effort_valid = accept_click.notna() & reject_click.notna()\
df_main["EFFORT_VALID"] = effort_valid.astype(int)\
\
# Effort indicators\
df_main["MECH_EE_ClickAsymmetry"] = np.where(\
    effort_valid & (reject_click > accept_click), 1, 0\
)\
\
if col_hidden_reject:\
    df_main["MECH_EE_HiddenReject"] = to_binary_yes_no(df_main[col_hidden_reject]).fillna(0).astype(int)\
else:\
    df_main["MECH_EE_HiddenReject"] = 0\
\
# Attention indicators\
if col_primary_accept:\
    df_main["MECH_AE_PrimaryAccept"] = to_binary_yes_no(df_main[col_primary_accept]).fillna(0).astype(int)\
else:\
    df_main["MECH_AE_PrimaryAccept"] = 0\
\
if col_accept_prom and col_reject_prom:\
    accept_prom = to_numeric(df_main[col_accept_prom])\
    reject_prom = to_numeric(df_main[col_reject_prom])\
    df_main["MECH_AE_ProminenceAsymmetry"] = np.where(\
        accept_prom.notna() & reject_prom.notna() & (accept_prom > reject_prom), 1, 0\
    )\
else:\
    df_main["MECH_AE_ProminenceAsymmetry"] = 0\
\
# Cognitive-load indicators\
# IMPORTANT: compute on Layer-2 subset, then merge back to main as zeros for non-L2 interfaces\
df_main["MECH_CL_HighComplexity"] = 0\
df_main["MECH_CL_HighInfoDensity"] = 0\
df_main["MECH_CL_HighToggleVolume"] = 0\
df_main["MECH_CL_GermaneSuppression"] = 0\
\
if len(df_l2) > 0:\
    if col_complexity:\
        complexity = to_numeric(df_l2[col_complexity])\
        df_main.loc[df_l2.index, "MECH_CL_HighComplexity"] = np.where(complexity >= 20, 1, 0)\
\
    if col_info_density:\
        info_density = to_numeric(df_l2[col_info_density])\
        df_main.loc[df_l2.index, "MECH_CL_HighInfoDensity"] = np.where(info_density >= 4, 1, 0)\
\
    if col_toggle_count:\
        toggle_count = to_numeric(df_l2[col_toggle_count])\
        df_main.loc[df_l2.index, "MECH_CL_HighToggleVolume"] = np.where(toggle_count >= 10, 1, 0)\
\
    if col_germane:\
        germane = to_binary_yes_no(df_l2[col_germane]).fillna(0).astype(int)\
        df_main.loc[df_l2.index, "MECH_CL_GermaneSuppression"] = germane.values\
\
# =========================================================\
# 6. Composite scores\
#    Use the manuscript-consistent composite definition\
# =========================================================\
df_main["EFFORT_SCORE"] = df_main["MECH_EE_ClickAsymmetry"] + df_main["MECH_EE_HiddenReject"]\
df_main["ATTENTION_SCORE"] = df_main["MECH_AE_PrimaryAccept"] + df_main["MECH_AE_ProminenceAsymmetry"]\
\
# manuscript-consistent CL score:\
# if your paper excludes toggle volume from final CL score, keep it excluded here\
df_main["COGNITIVE_LOAD_SCORE"] = (\
    df_main["MECH_CL_HighComplexity"]\
    + df_main["MECH_CL_HighInfoDensity"]\
    + df_main["MECH_CL_GermaneSuppression"]\
)\
\
df_main["ACLDP_TOTAL_SCORE"] = (\
    df_main["EFFORT_SCORE"]\
    + df_main["ATTENTION_SCORE"]\
    + df_main["COGNITIVE_LOAD_SCORE"]\
)\
\
# derived non-tautological DV for OLS:\
# use standardized total score? no\
# use total score? still tautological if predictors are exact components\
# Better: use a structural outcome not mechanically identical to predictors\
# For publication-valid Stage 2, use ACLDP_TOTAL_SCORE descriptively + correlations,\
# and for OLS use a reduced-form target:\
#   "Manipulation intensity excluding the focal predictor family" is awkward.\
# A better practical choice is to model ACLDP_TOTAL_SCORE using *indicator-level controls*\
# OR present OLS as exploratory using standardized family scores but excluding direct sum relation.\
#\
# Here we compute an exploratory model of cognitive-load burden / interface burden, but\
# to stay close to your framing, we use:\
#   DV = ACLDP_TOTAL_SCORE\
#   predictors = ATTENTION_SCORE, EFFORT_SCORE, COGNITIVE_LOAD_SCORE\
# This remains mechanically related.\
#\
# Therefore, publication-valid recommendation:\
# do NOT use OLS on total score built from the same family scores unless you state it is descriptive.\
# Instead, model a structural outcome:\
#   DV = MECH_EE_HiddenReject\
#   and an ecosystem model on ACLDP_TOTAL_SCORE.\
#\
# If you still want an interaction model, use a continuous non-identical target if present.\
# Fallback target below:\
#   CL burden proxy if available.\
#\
# We'll implement:\
#   OLS exploratory ecosystem model on ACLDP_TOTAL_SCORE\
#   with CMP, sector, and Layer-2 info density (not the same as direct sum components)\
# and a Stage 2 correlation matrix on composite scores.\
#\
# For your requested OLS interaction table, we fit it but flag it as descriptive-only.}
