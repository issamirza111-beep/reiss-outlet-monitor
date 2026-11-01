#!/usr/bin/env python3
"""
Reiss Outlet Monitor
--------------------
Crawls the Reiss UK online outlet, remembers every item it has seen, and
sends a push notification when a NEW item lands in the outlet (and,
optionally, when an existing outlet item drops further in price).

No third-party packages needed — standard library only (Python 3.9+).

Notifications (set any/all via environment variables):
  NTFY_TOPIC          -> free push to your phone via the ntfy app (easiest)
  TELEGRAM_BOT_TOKEN  -> plus TELEGRAM_CHAT_ID, for Telegram messages
If none are set, new items are just printed to the console.
"""

import gzip
import html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ============================ SETTINGS ===================================
# Edit these to suit. Everything else can stay as it is.

BASE = "https://www.reiss.com"   # UK site (prices in £)

# Which outlet pages to watch: men's outlet, filtered to size M and size L.
# Each entry can list backup URLs; the first one that returns items is used.
# You can paste any filtered outlet URL path from reiss.com here.
# (Whole men's outlet, no size filter: "/shop/feat-sale-gender-men-0")
SECTIONS = {
    "M": ["/shop/feat-sale/gender-men-size-medium",
          "/shop/feat-sale-gender-men/size-medium"],
    "L": ["/shop/feat-sale/gender-men-size-large",
          "/shop/feat-sale-gender-men/size-large"],
}

# Only alert for items whose name contains one of these words
# (case-insensitive). Leave empty [] to be alerted about everything.
KEYWORDS = []            # e.g. ["blazer", "overcoat", "cashmere", "loafer"]

# Ignore items whose name contains any of these words.
EXCLUDE_KEYWORDS = []    # e.g. ["sock", "tie", "pocket square"]

# Only alert if the outlet price is at or below this (£). None = no limit.
MAX_PRICE = None

# Also alert when an item already in the outlet gets cheaper?
ALERT_PRICE_DROPS = True

# Safety limits so the crawl stays polite.
MAX_PAGES_PER_SECTION = 200      # ~12 items/page -> 2,400 items
DELAY_BETWEEN_PAGES = (1.5, 3.0) # random pause in seconds

STATE_FILE = os.environ.get(
    "STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_items.json")
)
# =========================================================================

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

# A product card link looks like:
#   <a href="https://www.reiss.com/style/su962936/g63448"
#      title="Argyle-Knit Press-Stud Polo Shirt in Camel Brown (G63448) | £134">
ANCHOR_RE = re.compile(r"<a\b[^>]*>", re.I)
HREF_RE = re.compile(r'href\s*=\s*"([^"]*/style/([a-z0-9]+)/([a-z0-9]+))[^"]*"', re.I)
TITLE_RE = re.compile(r'title\s*=\s*"([^"]+)"', re.I)
TITLE_PARSE_RE = re.compile(
    r"^(?P<name>.+?)\s+in\s+(?P<colour>.+?)\s*\((?P<code>[A-Za-z0-9]+)\)\s*\|\s*"
    r"(?P<cur>[£$€])\s*(?P<price>[\d,]+(?:\.\d+)?)",
)
NEXT_PAGE_RE = re.compile(r"[?&]p=(\d+)")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def fetch(url, retries=3):
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept-Encoding": "gzip",
        "Cache-Control": "no-cache",
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    data = gzip.decompress(data)
                return data.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (403, 429):
                log(f"  Blocked/rate-limited ({e.code}) on {url}; backing off")
                time.sleep(10 * attempt)
            elif e.code == 404:
                return ""
            else:
                time.sleep(3 * attempt)
        except Exception as e:  # network hiccup
            last_err = e
            time.sleep(3 * attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def parse_products(page_html):
    """Return {code: {...}} for every product card on a listing page."""
    items = {}
    for tag in ANCHOR_RE.findall(page_html):
        h = HREF_RE.search(tag)
        t = TITLE_RE.search(tag)
        if not h or not t:
            continue
        title = html.unescape(t.group(1)).strip()
        m = TITLE_PARSE_RE.match(title)
        if not m:
            continue  # colour-swatch links only have a colour as title
        code = m.group("code").upper()
        url = h.group(1)
        if url.startswith("/"):
            url = BASE + url
        url = url.split("?")[0]
        items[code] = {
            "code": code,
            "name": m.group("name").strip(),
            "colour": m.group("colour").strip(),
            "price": float(m.group("price").replace(",", "")),
            "currency": m.group("cur"),
            "url": url,
        }
    return items


def page_url(path, page):
    url = BASE + path
    if page > 1:
        url += ("&" if "?" in url else "?") + f"p={page}"
    return url


def crawl_section(label, path):
    found = {}
    for page in range(1, MAX_PAGES_PER_SECTION + 1):
        html_text = fetch(page_url(path, page))
        items = parse_products(html_text)
        new_on_page = {k: v for k, v in items.items() if k not in found}
        for v in new_on_page.values():
            v["section"] = label
        found.update(new_on_page)
        if page == 1:
            total = re.search(r"\((\d[\d,]*)\)\s*</", html_text)
            if total:
                log(f"{label}: site reports {total.group(1)} items")
        if not new_on_page:
            break  # ran past the last page
        if not re.search(rf'[?&]p={page + 1}\b', html_text):
            # No link to the next page on this one -> last page
            break
        time.sleep(random.uniform(*DELAY_BETWEEN_PAGES))
    log(f"{label}: collected {len(found)} items across {page} page(s)")
    return found


def matches_filters(item):
    name = f"{item['name']} {item['colour']}".lower()
    if KEYWORDS and not any(k.lower() in name for k in KEYWORDS):
        return False
    if any(k.lower() in name for k in EXCLUDE_KEYWORDS):
        return False
    if MAX_PRICE is not None and item["price"] > MAX_PRICE:
        return False
    return True


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(tmp, STATE_FILE)


# ----------------------------- notifications -----------------------------

def notify_ntfy(title, body, click_url=None, tags="shopping"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    headers = {"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Tags": tags}
    if click_url:
        headers["Click"] = click_url
    req = urllib.request.Request(
        f"{server}/{topic}", data=body.encode("utf-8"), headers=headers, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        log(f"  ntfy failed: {e}")


def notify_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    data = urllib.parse.urlencode(
        {"chat_id": chat, "text": text, "disable_web_page_preview": "false"}
    ).encode()
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20
        ).read()
    except Exception as e:
        log(f"  Telegram failed: {e}")


def fmt(item):
    return f"{item['name']} — {item['colour']}\n{item['currency']}{item['price']:g} · Size {item['section']}"


def send_alerts(new_items, drops):
    if not new_items and not drops:
        return
    # One push per item when there are only a few; a digest when there are many.
    if len(new_items) + len(drops) <= 8:
        for it in new_items:
            notify_ntfy("🆕 New in Reiss outlet", fmt(it), it["url"], "new,shopping")
            notify_telegram(f"🆕 New in Reiss outlet\n{fmt(it)}\n{it['url']}")
        for it, old in drops:
            body = fmt(it) + f" (was {it['currency']}{old:g})"
            notify_ntfy("📉 Reiss outlet price drop", body, it["url"], "chart_with_downwards_trend")
            notify_telegram(f"📉 Price drop\n{body}\n{it['url']}")
    else:
        lines = [f"• {i['name']} ({i['colour']}) {i['currency']}{i['price']:g}" for i in new_items]
        lines += [f"• ↓ {i['name']} ({i['colour']}) {i['currency']}{i['price']:g} (was {o:g})" for i, o in drops]
        head = f"{len(new_items)} new item(s), {len(drops)} price drop(s)"
        digest = "\n".join(lines[:40]) + ("\n…and more" if len(lines) > 40 else "")
        outlet = BASE + "/sales"
        notify_ntfy(f"🛍 Reiss outlet: {head}", digest, outlet, "shopping")
        tg_lines = [f"• {i['name']} ({i['colour']}) {i['currency']}{i['price']:g}\n  {i['url']}" for i in new_items]
        tg_lines += [f"• ↓ {i['name']} {i['currency']}{i['price']:g} (was {o:g})\n  {i['url']}" for i, o in drops]
        for chunk_start in range(0, len(tg_lines), 25):
            notify_telegram(f"🛍 Reiss outlet: {head}\n\n" + "\n".join(tg_lines[chunk_start:chunk_start + 25]))


# --------------------------------- main ----------------------------------

def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = load_state()
    first_run = state is None
    if first_run:
        state = {"items": {}, "last_run": None}

    current = {}
    for label, paths in SECTIONS.items():
        if isinstance(paths, str):
            paths = [paths]
        got = {}
        for path in paths:
            try:
                got = crawl_section(label, path)
            except Exception as e:
                log(f"{label}: ERROR on {path}: {e}")
                got = {}
            if got:
                break
            log(f"{label}: no items at {path}, trying next URL")
        for code, item in got.items():
            if code in current:  # same item available in several sizes
                sizes = current[code]["section"].split("/")
                if label not in sizes:
                    current[code]["section"] = "/".join(sizes + [label])
            else:
                current[code] = item

    if not current:
        log("Got 0 items — the site may be blocking this machine or the page layout changed. "
            "State left untouched.")
        sys.exit(1)

    seen = state["items"]
    new_items, drops = [], []
    for code, item in current.items():
        prev = seen.get(code)
        if prev is None:
            item["first_seen"] = now
            if not first_run and matches_filters(item):
                new_items.append(item)
        else:
            item["first_seen"] = prev.get("first_seen", now)
            if (ALERT_PRICE_DROPS and not first_run
                    and item["price"] < prev.get("price", item["price"])
                    and matches_filters(item)):
                drops.append((item, prev["price"]))
        item["last_seen"] = now
        item["in_outlet"] = True
        seen[code] = item

    # Mark items that have left the outlet (sold out / removed). If one
    # returns later it will NOT re-alert as new, which avoids noise.
    for code, item in seen.items():
        if code not in current:
            item["in_outlet"] = False

    state["last_run"] = now
    save_state(state)

    if first_run:
        log(f"First run: recorded {len(current)} existing outlet items as the baseline. "
            "You'll be alerted about anything added from now on.")
        notify_ntfy("✅ Reiss outlet monitor is live",
                    f"Tracking {len(current)} items. You'll get a push when new ones are added.",
                    BASE + "/sales", "white_check_mark")
        notify_telegram(f"✅ Reiss outlet monitor is live — tracking {len(current)} items.")
        return

    log(f"{len(new_items)} new item(s), {len(drops)} price drop(s)")
    for it in new_items:
        log(f"  NEW  {fmt(it).replace(chr(10), ' | ')}  {it['url']}")
    for it, old in drops:
        log(f"  DROP {fmt(it).replace(chr(10), ' | ')} (was {old:g})  {it['url']}")
    send_alerts(new_items, drops)


if __name__ == "__main__":
    main()
