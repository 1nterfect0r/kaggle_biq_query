
#!/usr/bin/env python3
# SAP Community scraper
# - Flat answers with text-only fields (now with light Markdown)
# - Accepted detection (incl. "Accepted Solutions" section)
# - Robust created_at & upvotes
# - NO question object; store `question_text` and `question_upvotes` on the ContentItem
# - Tags include "custom-view-associated-products" entries
# - Links/Images in body -> Markdown (anchor/img only, conservative)
# - Mentions like @User are kept as plain text (no Markdown link)
# ---------------------------------------------------------------------

import argparse
import gzip
import json
import logging
import random
import re
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup, Tag, NavigableString

# ----------------------
# HTTP helpers
# ----------------------

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "close",
}


def http_get(url: str, timeout: int = 30, max_retries: int = 3, sleep_range: Tuple[float, float] = (1.0, 2.0)) -> requests.Response:
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp
            else:
                logging.warning("Non-200 status %s for %s", resp.status_code, url)
        except Exception as exc:
            last_exc = exc
            logging.warning("Request error on attempt %s for %s: %s", attempt, url, exc)
        time.sleep(random.uniform(*sleep_range) * attempt)
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Failed to GET {url}")


# ----------------------
# Sitemap parsing
# ----------------------

def parse_sitemap(url: str) -> List[Dict]:
    resp = http_get(url)
    content = resp.content
    if url.lower().endswith(".gz") or resp.headers.get("Content-Type", "").startswith("application/x-gzip"):
        try:
            content = gzip.decompress(content)
        except OSError:
            pass
    soup = BeautifulSoup(content, "xml")
    urls = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        lastmod = url_tag.find("lastmod")
        if loc and loc.text:
            urls.append({
                "loc": loc.text.strip(),
                "lastmod": lastmod.text.strip() if lastmod and lastmod.text else None,
                "source_sitemap": url,
            })
    return urls


# ----------------------
# Utilities
# ----------------------

ISO_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:\d{2})?")
LRM_RLM = re.compile(r"[\u200e\u200f]")  # left/right-to-left marks

def normalize_whitespace(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = LRM_RLM.sub("", s)
    s = s.replace("\u00a0", " ")  # replace non-breaking spaces with normal spaces
    return re.sub(r"\s+", " ", s).strip()


def extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    blocks = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        content = (tag.string or tag.text or "").strip()
        if not content:
            continue
        try:
            blocks.append(json.loads(content))
        except Exception:
            try:
                fixed = re.sub(r",\s*}", "}", content)
                fixed = re.sub(r",\s*]", "]", fixed)
                blocks.append(json.loads(fixed))
            except Exception:
                continue
    return blocks


def uniq_push(arr: List[str], val: Optional[str]):
    if not val:
        return
    val_norm = val.strip()
    if not val_norm:
        return
    lower_set = {x.lower() for x in arr}
    if val_norm.lower() not in lower_set:
        arr.append(val_norm)


# ----------------------
# Light HTML -> Markdown converter (anchor/img + simple blocks)
# ----------------------

BLOCK_BREAK_TAGS = {"p", "div", "section", "article"}
LINE_BREAK_TAGS = {"br", "hr", "li"}

def node_to_markdown(node: Tag, base_url: str) -> str:
    """Conservative HTML->MD: supports links (except @mentions) and images; keeps text; collapses whitespace.
    Adds newlines for simple block tags and list items.
    """
    pieces: List[str] = []

    def walk(n):
        if isinstance(n, NavigableString):
            pieces.append(str(n))
            return
        if not isinstance(n, Tag):
            return
        name = n.name.lower()

        # Skip unwanted nodes
        if name in ("script", "style", "noscript"):
            return

        if name == "a":
            href = n.get("href", "").strip()
            text = n.get_text(" ", strip=True)
            # If it's an @mention, keep plain text (no link)
            if text.startswith("@"):
                pieces.append(text)
                return
            if href:
                # absolutize relative hrefs
                try:
                    href = urljoin(base_url, href)
                except Exception:
                    pass
                pieces.append(f"[{text}]({href})")
            else:
                pieces.append(text)
            return

        if name == "img":
            src = n.get("src", "").strip()
            alt = n.get("alt", "").strip() or n.get("title", "").strip()
            if src:
                try:
                    src = urljoin(base_url, src)
                except Exception:
                    pass
                pieces.append(f"![{alt}]({src})")
            return

        # Lists
        if name in ("ul", "ol"):
            for li in n.find_all("li", recursive=False):
                pieces.append("\n- ")
                walk(li)
            pieces.append("\n")
            return

        # Code (inline)
        if name in ("code", "kbd"):
            pieces.append("`" + n.get_text("", strip=True) + "`")
            return

        # Bold / italic: just text
        if name in ("strong", "b", "em", "i", "u", "span"):
            for c in n.children:
                walk(c)
            return

        # Block breaks
        if name in BLOCK_BREAK_TAGS:
            if pieces and not pieces[-1].endswith("\n"):
                pieces.append("\n")
            for c in n.children:
                walk(c)
            if not (pieces and pieces[-1].endswith("\n")):
                pieces.append("\n")
            return

        if name in LINE_BREAK_TAGS:
            for c in n.children:
                walk(c)
            pieces.append("\n")
            return

        # Default: recurse
        for c in n.children:
            walk(c)

    walk(node)
    md = "".join(pieces)
    # Replace non-standard spaces and zero-width characters
    md = md.replace("\u00a0", " ").replace("\u202f", " ").replace("\u2007", " ")
    import re as _re_md
    md = _re_md.sub(r"[\u200b\u200c\u200d]", "", md)

    # Collapse whitespace and tidy newlines
    md = re.sub(r"[ \t]+", " ", md)
    md = re.sub(r"\n\s*\n\s*\n+", "\n\n", md)  # max 1 blank line
    md = md.strip()
    return md or ""


# ----------------------
# Core extraction (rest unchanged from previous version)
# ----------------------

ACCEPTED_HINT_TEXT = re.compile(r"\bAccepted\s+Solution\b|\bAccepted\s+Answers?\b", re.I)
ACCEPTED_CLASS_RE = re.compile(
    r"\blia-accepted-solution\b|\blia-solution-accepted\b|\blia-message-accepted-solution\b|\blia-list-row-thread-solved\b|\baccepted\b|\bsolution\b",
    re.I
)


from dataclasses import dataclass

@dataclass
class Answer:
    message_id: Optional[str] = None
    message_url: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[str] = None  # ISO8601 if available
    text: Optional[str] = None  # Markdown
    is_accepted: bool = False
    upvotes: Optional[int] = None


@dataclass
class ContentItem:
    url: str
    lastmod_from_sitemap: Optional[str]
    content_type: str  # "qna" | "blog" | "other"
    title: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None  # ISO8601 if possible
    updated_at: Optional[str] = None    # ISO8601 if possible
    board: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # flattened question fields (Markdown text)
    question_text: Optional[str] = None
    question_upvotes: Optional[int] = None

    # answers (includes comments)
    answers: List[Answer] = field(default_factory=list)
    reply_count: Optional[int] = None


def detect_content_type(parsed_url: str) -> str:
    path = urlparse(parsed_url).path.lower()
    if "/qaq-p/" in path or "/qa-p/" in path:
        return "qna"
    if "/blogs/" in path or "/blog/" in path:
        return "blog"
    return "other"


def extract_common_fields(soup: BeautifulSoup) -> Dict[str, Optional[str]]:
    title = None
    if soup.title and soup.title.string:
        title = normalize_whitespace(soup.title.string)
    ogt = soup.find("meta", {"property": "og:title"})
    if ogt and ogt.get("content"):
        title = normalize_whitespace(ogt["content"])

    author = None
    for selector in [
        ('meta', {"name": "author"}),
        ('meta', {"property": "article:author"}),
    ]:
        tag = soup.find(*selector)
        if tag and tag.get("content"):
            author = normalize_whitespace(tag["content"])
            break

    published = None
    updated = None
    for prop in ["article:published_time", "og:article:published_time"]:
        tag = soup.find("meta", {"property": prop})
        if tag and tag.get("content"):
            published = normalize_whitespace(tag["content"])
            break
    for prop in ["article:modified_time", "og:updated_time"]:
        tag = soup.find("meta", {"property": prop})
        if tag and tag.get("content"):
            updated = normalize_whitespace(tag["content"])
            break

    tags: List[str] = []

    # "Classic" tags
    for t in soup.select('a[rel~="tag"], a[href*="/t5/tag/"], a[class*="Tag"]'):
        txt = normalize_whitespace(t.get_text())
        uniq_push(tags, txt)

    # SAP Managed Tags (custom-view-associated-products)
    for a in soup.select('div.custom-view-associated-products li.lia-link-navigation a'):
        txt = normalize_whitespace(a.get_text())
        uniq_push(tags, txt)

    return {
        "title": title,
        "author": author,
        "published_at": published,
        "updated_at": updated,
        "tags": tags,
    }


def extract_board_from_url(url: str) -> Optional[str]:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        slug = parts[1]
        if slug.startswith("human-capital-management-q-a"):
            return "hcm-questions"
    return None


def extract_json_ld(soup: BeautifulSoup) -> List[Dict]:
    blocks = []
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        content = (tag.string or tag.text or "").strip()
        if not content:
            continue
        try:
            blocks.append(json.loads(content))
        except Exception:
            try:
                fixed = re.sub(r",\s*}", "}", content)
                fixed = re.sub(r",\s*]", "]", fixed)
                blocks.append(json.loads(fixed))
            except Exception:
                continue
    return blocks


def extract_json_ld_accepted_ids(soup: BeautifulSoup) -> Set[str]:
    ids: Set[str] = set()
    for block in extract_json_ld(soup):
        try:
            nodes = block.get("@graph") if isinstance(block.get("@graph"), list) else [block]
            for node in nodes:
                types = node.get("@type") or node.get("type") or []
                if isinstance(types, str):
                    types = [types]
                if not any(str(t).lower() == "qapage" for t in types):
                    continue
                main = node.get("mainEntity") or {}
                if isinstance(main, list) and main:
                    main = main[0]
                accepted = main.get("acceptedAnswer")
                if not accepted:
                    continue
                if not isinstance(accepted, list):
                    accepted = [accepted]
                for a in accepted:
                    url = a.get("url") or a.get("mainEntityOfPage") or ""
                    m = re.search(r"#M(\d+)", url or "")
                    if m:
                        ids.add(m.group(1))
        except Exception:
            continue
    return ids


def parse_dt_string(s: str) -> Optional[str]:
    if not s:
        return None
    s = normalize_whitespace(s)
    fmts = [
        "%Y %b %d %I:%M %p",
        "%Y %b %d %H:%M",
        "%b %d %Y %I:%M %p",
        "%b %d %Y %H:%M",
        "%Y %b %d",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y %b %d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt.isoformat(timespec="seconds")
        except Exception:
            continue
    return None


def parse_datetime_candidate(container: Tag) -> Optional[str]:
    t = container.find("time")
    if t and (t.get("datetime") or t.get("title")):
        val = t.get("datetime") or t.get("title")
        val = normalize_whitespace(val)
        if val and ISO_PATTERN.search(val):
            return ISO_PATTERN.search(val).group(0)
        parsed = parse_dt_string(val)
        if parsed:
            return parsed

    friendly = container.select_one('.lia-message-post-date .DateTime .local-friendly-date[title]')
    if friendly:
        val = friendly.get("title")
        parsed = parse_dt_string(val)
        if parsed:
            return parsed

    dt_wrap = container.select_one('.lia-message-post-date .DateTime')
    if dt_wrap:
        ld = dt_wrap.find("span", class_=re.compile(r"\blocal-date\b"))
        lt = dt_wrap.find("span", class_=re.compile(r"\blocal-time\b"))
        if ld and lt:
            composed = f"{normalize_whitespace(ld.get_text())} {normalize_whitespace(lt.get_text())}"
            parsed = parse_dt_string(composed)
            if parsed:
                return parsed

    candidates = container.select('[itemprop*="date"], [property*="date"], [data-lia-message-time], [data-lia-message-timestamp]')
    for tag in candidates:
        for attr in ["datetime", "content", "data-lia-message-time", "data-lia-message-timestamp", "title"]:
            val = tag.get(attr)
            if not val:
                continue
            val = normalize_whitespace(val)
            if not val:
                continue
            if ISO_PATTERN.search(val):
                return ISO_PATTERN.search(val).group(0)
            parsed = parse_dt_string(val)
            if parsed:
                return parsed

    for el in container.find_all(True):
        for attr_val in el.attrs.values():
            if isinstance(attr_val, str):
                val = normalize_whitespace(attr_val)
                if ISO_PATTERN.search(val):
                    return ISO_PATTERN.search(val).group(0)

    text = normalize_whitespace(container.get_text(" "))
    if ISO_PATTERN.search(text):
        return ISO_PATTERN.search(text).group(0)
    m = re.search(r"\b(\d{4}\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}\s*(AM|PM)?)\b", text)
    if m:
        parsed = parse_dt_string(m.group(1))
        if parsed:
            return parsed

    return None


def extract_upvotes(container: Tag) -> Optional[int]:
    for el in container.find_all(attrs={"aria-label": True}):
        label = str(el.get("aria-label"))
        if re.search(r"kudo|like|vote", label, re.I):
            m = re.search(r"\d+", label)
            if m:
                return int(m.group(0))

    for el in container.find_all(True, class_=re.compile(r"kudo|likes?|vote|rating|count", re.I)):
        txt = el.get_text(" ").strip()
        m = re.search(r"\d+", txt)
        if m:
            return int(m.group(0))
        for attr, val in el.attrs.items():
            if isinstance(val, str) and (attr.startswith("data-") or attr in ("data-count", "data-kudos-count")):
                m = re.search(r"\d+", val)
                if m:
                    return int(m.group(0))

    el = container.select_one('[id*="kudos"], [class*="kudos"]')
    if el:
        m = re.search(r"\d+", el.get_text(" "))
        if m:
            return int(m.group(0))

    return None


def get_anchor_mid(div: Tag) -> Optional[str]:
    el = div.find(id=re.compile(r"^M\d+$"))
    if el:
        m = re.match(r"M(\d+)", el.get("id", ""))
        if m:
            return m.group(1)
    a = div.find("a", href=re.compile(r"#M\d+"))
    if a and a.has_attr("href"):
        m = re.search(r"#M(\d+)", a["href"])
        if m:
            return m.group(1)
    return None


def get_msg_id(div: Tag) -> Optional[str]:
    mid = get_anchor_mid(div)
    if mid:
        return mid
    if div.has_attr("data-lia-message-uid"):
        return str(div["data-lia-message-uid"])
    if div.has_attr("id"):
        m = re.search(r"message-(\d+)", div["id"])
        if m:
            return m.group(1)
    return None


def is_question_div(div: Tag) -> bool:
    classes = " ".join(div.get("class", [])).lower()
    return bool(re.search(r"qanda[- ]?question|message-view-qanda-question|thread-topic|lia-message-view-question", classes))


def container_has_accepted_marker_for_message(div: Tag) -> bool:
    classes_self = " ".join(div.get("class", [])) or ""
    if ACCEPTED_CLASS_RE.search(classes_self):
        return True

    mv = div.find("div", class_=re.compile(r"\bMessageView\b"))
    if mv:
        classes_mv = " ".join(mv.get("class", [])) or ""
        if ACCEPTED_CLASS_RE.search(classes_mv):
            return True
        if mv.find(string=ACCEPTED_HINT_TEXT):
            return True

    return False


def extract_body_markdown(container: Tag, page_url: str) -> Optional[str]:
    body_div = container.find("div", {"class": re.compile(r"(lia-message-body|lia-message-body-content|lia-article-body)")})
    if not body_div:
        return None
    for bad in body_div.find_all(["script", "style", "noscript"]):
        bad.decompose()
    md = node_to_markdown(body_div, base_url=page_url)
    return md or None


def build_answer_from_div(div: Tag, page_url: str) -> Answer:
    msg_id = get_msg_id(div)
    msg_url = f"{page_url}#M{msg_id}" if msg_id else None

    author = None
    auth_tag = div.find(["a", "span"], {"class": re.compile(r"(lia-user-name|lia-component-author-name)")})
    if auth_tag:
        author = normalize_whitespace(auth_tag.get_text())

    text_md = extract_body_markdown(div, page_url)

    created_at = parse_datetime_candidate(div)
    upvotes = extract_upvotes(div)

    is_accepted = container_has_accepted_marker_for_message(div)

    return Answer(
        message_id=msg_id,
        message_url=msg_url,
        author=author,
        created_at=created_at,
        text=text_md,
        is_accepted=is_accepted,
        upvotes=upvotes,
    )


def extract_flat_qna(soup: BeautifulSoup, page_url: str):
    containers = list(soup.select('div[id^="message-"], div[data-lia-message-uid]'))

    accepted_wrappers = soup.select(
        'div.ComponentToggler.lia-component-solutions-with-toggle, '
        'div.lia-accepted-solution, div.lia-message-accepted-solution, '
        'div.lia-solution-accepted, div.lia-list-row-thread-solved'
    )
    for wrap in accepted_wrappers:
        inner_msgs = wrap.select('div[id^="message-"], div[data-lia-message-uid]')
        for m in inner_msgs:
            if m not in containers:
                containers.append(m)

    if not containers:
        return None, None, [], 0

    answers_by_id: Dict[str, Answer] = {}
    order: List[str] = []

    for div in containers:
        mid = get_msg_id(div)
        if not mid:
            continue
        ans = build_answer_from_div(div, page_url)
        if mid in answers_by_id:
            base = answers_by_id[mid]
            base.is_accepted = base.is_accepted or ans.is_accepted
            if not base.text and ans.text:
                base.text = ans.text
            if not base.created_at and ans.created_at:
                base.created_at = ans.created_at
            if base.upvotes is None and ans.upvotes is not None:
                base.upvotes = ans.upvotes
            continue
        answers_by_id[mid] = ans
        order.append(mid)

    question_id = None
    for div in containers:
        if is_question_div(div):
            question_id = get_msg_id(div)
            break
    if question_id is None and order:
        question_id = order[0]

    question_text = None
    question_upvotes = None
    if question_id and question_id in answers_by_id:
        q_ans = answers_by_id.pop(question_id)
        order.remove(question_id)
        question_text = q_ans.text
        question_upvotes = q_ans.upvotes

    answers: List[Answer] = [answers_by_id[mid] for mid in order]

    for mid in extract_json_ld_accepted_ids(soup):
        if mid in answers_by_id:
            answers_by_id[mid].is_accepted = True

    return question_text, question_upvotes, answers, len(answers)


def parse_qna_page(url: str, html: bytes) -> ContentItem:
    soup = BeautifulSoup(html, "lxml")

    common = extract_common_fields(soup)
    board = extract_board_from_url(url)

    question_text, question_upvotes, answers, reply_count = extract_flat_qna(soup, url)

    return ContentItem(
        url=url,
        lastmod_from_sitemap=None,
        content_type="qna",
        title=common["title"],
        author=common["author"],
        published_at=common["published_at"],
        updated_at=common["updated_at"],
        board=board,
        tags=common["tags"],
        question_text=question_text,
        question_upvotes=question_upvotes,
        answers=answers or [],
        reply_count=reply_count or 0,
    )


def parse_blog_page(url: str, html: bytes) -> ContentItem:
    soup = BeautifulSoup(html, "lxml")
    common = extract_common_fields(soup)

    article = soup.find("div", {"class": re.compile(r"(lia-article-body|lia-message-body|lia-message-body-content)")}) or soup.find("article")
    question_text = node_to_markdown(article, base_url=url) if article else None
    question_upvotes = None

    answers: List[Answer] = []
    comment_containers = soup.select('div[class*="comment"] div[id^="message-"], div[id^="message-"].lia-message-comment')
    seen = set()
    for div in comment_containers:
        mid = get_msg_id(div)
        if mid and mid in seen:
            continue
        if mid:
            seen.add(mid)
        ans = build_answer_from_div(div, url)
        ans.is_accepted = False  # blogs don't have accepted answers
        answers.append(ans)

    return ContentItem(
        url=url,
        lastmod_from_sitemap=None,
        content_type="blog",
        title=common["title"],
        author=common["author"],
        published_at=common["published_at"],
        updated_at=common["updated_at"],
        tags=common["tags"],
        question_text=question_text,
        question_upvotes=question_upvotes,
        answers=answers,
        reply_count=len(answers),
    )


def parse_generic_page(url: str, html: bytes) -> ContentItem:
    soup = BeautifulSoup(html, "lxml")
    common = extract_common_fields(soup)
    question_text = None
    question_upvotes = None
    return ContentItem(
        url=url,
        lastmod_from_sitemap=None,
        content_type="other",
        title=common["title"],
        author=common["author"],
        published_at=common["published_at"],
        updated_at=common["updated_at"],
        tags=common["tags"],
        question_text=question_text,
        question_upvotes=question_upvotes,
        answers=[],
        reply_count=0,
    )


def scrape_from_sitemaps(
    sitemap_urls: List[str],
    limit: int = 10,
    timeout: int = 30,
    sleep_range: Tuple[float, float] = (1.0, 2.0),
    max_retries: int = 3,
) -> List[ContentItem]:
    entries = []
    for sm in sitemap_urls:
        try:
            urls = parse_sitemap(sm)
        except Exception as exc:
            logging.error("Failed to parse sitemap %s: %s", sm, exc)
            continue
        entries.extend(urls)
    if not entries:
        logging.warning("No entries found in provided sitemaps.")
        return []

    def sort_key(e):
        lm = e.get("lastmod")
        if not lm:
            return 0
        try:
            return int(datetime.fromisoformat(lm.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0

    entries.sort(key=sort_key, reverse=True)
    entries = entries[:limit]

    results: List[ContentItem] = []
    for idx, e in enumerate(entries, 1):
        url = e["loc"]
        logging.info("Fetching %d/%d: %s", idx, len(entries), url)
        try:
            resp = http_get(url, timeout=timeout, max_retries=max_retries, sleep_range=sleep_range)
        except Exception as exc:
            logging.warning("Skipping %s due to fetch error: %s", url, exc)
            continue

        ctype = detect_content_type(url)
        if ctype == "qna":
            item = parse_qna_page(url, resp.content)
        elif ctype == "blog":
            item = parse_blog_page(url, resp.content)
        else:
            item = parse_generic_page(url, resp.content)
        item.lastmod_from_sitemap = e.get("lastmod")
        results.append(item)

        time.sleep(random.uniform(*sleep_range))
    return results


def save_jsonl(items: List[ContentItem], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            obj = asdict(it)
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def save_json(items: List[ContentItem], path: str) -> None:
    arr = [asdict(it) for it in items]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Scrape SAP Community pages from sitemap(s).")
    parser.add_argument("--sitemap", action="append", required=True, help="Sitemap URL (.xml or .xml.gz). Can be passed multiple times.")
    parser.add_argument("--limit", type=int, default=10, help="Max number of pages to fetch across all sitemaps (default: 10).")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds (default: 30).")
    parser.add_argument("--sleep-min", type=float, default=1.0, help="Min delay between requests in seconds (default: 1.0).")
    parser.add_argument("--sleep-max", type=float, default=2.0, help="Max delay between requests in seconds (default: 2.0).")
    parser.add_argument("--retries", type=int, default=3, help="Max HTTP retries per request (default: 3).")
    parser.add_argument("--out-jsonl", type=str, default="sap_pages.jsonl", help="Output JSONL file (default: sap_pages.jsonl).")
    parser.add_argument("--out-json", type=str, default="sap_pages.json", help="Output JSON file (default: sap_pages.json).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    items = scrape_from_sitemaps(
        sitemap_urls=args.sitemap,
        limit=args.limit,
        timeout=args.timeout,
        sleep_range=(args.sleep_min, args.sleep_max),
        max_retries=args.retries,
    )
    logging.info("Extracted %d items", len(items))

    save_jsonl(items, args.out_jsonl)
    save_json(items, args.out_json)
    logging.info("Saved %s and %s", args.out_jsonl, args.out_json)


if __name__ == "__main__":
    main()
