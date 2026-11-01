# Reiss Outlet Monitor

Pings your phone whenever a new item in **size M or L** is added to the Reiss UK
**men's outlet**, and when one of those items drops further in price. Each alert
shows which of your sizes it's available in (M, L or M/L).

It crawls every page of the outlet, keeps a list of item codes it has already
seen in `seen_items.json`, and alerts only on codes it hasn't seen before. The
first run just records what's there today, so you won't get 2,000 alerts.

---

## 1. Get notifications on your phone (2 minutes)

**Option A — ntfy (easiest, free, no account)**
1. Install the **ntfy** app (iOS / Android).
2. Tap **+**, subscribe to a topic with a hard-to-guess name, e.g. `reiss-outlet-issa-7f3k9`.
   Anyone who knows the name can read it, so make it unique.
3. Keep that name — it's your `NTFY_TOPIC`.

**Option B — Telegram**
1. Message **@BotFather** → `/newbot` → copy the bot token.
2. Send your new bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id": ...}`.
3. Those are `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

You can use both.

## 2. (Not working) Run it on GitHub's servers

Reiss currently blocks GitHub's servers (HTTP 403), so the schedule is paused.
Kept here in case that changes.

1. Create a free GitHub account → **New repository** (private is fine).
2. Upload everything in this folder, keeping the `.github/workflows/monitor.yml` path.
3. Repo **Settings → Secrets and variables → Actions → New repository secret**:
   add `NTFY_TOPIC` (and/or the two Telegram ones).
4. **Actions** tab → enable workflows → **Reiss outlet monitor → Run workflow**.
   You should get a "✅ monitor is live" push within ~5 minutes.

From then on it checks every 30 minutes. To change the frequency, edit the `cron`
line in `monitor.yml` (e.g. `"17 * * * *"` = hourly).

**Make the repo public.** Each check takes ~5–8 minutes, so 48 checks a day is
~10,000 Actions minutes a month — far over the 2,000 free minutes private repos
get, but unlimited and free on public repos. Your ntfy/Telegram secrets stay
hidden either way; the only thing visible is the list of Reiss items it has seen.
(If you'd rather keep it private, use hourly or every 2 hours instead.)

GitHub's scheduler can run a few minutes late at busy times, so expect alerts
within roughly 30–40 minutes of an item going live.

## 3. Run it on your Mac (recommended — Reiss blocks GitHub's servers)

In **Terminal**, paste (swap in your ntfy topic at the end):

```bash
curl -fsSL https://raw.githubusercontent.com/issamirza111-beep/reiss-outlet-monitor/main/mac/install.sh | bash -s -- YOUR-NTFY-TOPIC
```

It checks every 30 minutes while the Mac is awake (missed checks catch up on
wake). Files live in `~/reiss-monitor`; the log is `~/reiss-monitor/monitor.log`.

**Control it from your phone**
- **Pause / resume:** edit `control.txt` in this repo on GitHub → `off` / `on`.
  The Mac reads it before every check.
- **Change sizes, keywords, max price:** edit `reiss_monitor.py` here (or ask
  Claude to). The Mac downloads the latest version before every check.

**Remove it from the Mac**
```bash
curl -fsSL https://raw.githubusercontent.com/issamirza111-beep/reiss-outlet-monitor/main/mac/uninstall.sh | bash
```

---

## Customise (top of `reiss_monitor.py`)

| Setting | What it does |
|---|---|
| `SECTIONS` | Which outlet pages to watch. Paste any filtered reiss.com outlet URL path, e.g. your size only: `/shop/feat-sale/gender-men-size-medium` |
| `KEYWORDS` | Only alert for names containing these, e.g. `["blazer", "overcoat", "cashmere"]` |
| `EXCLUDE_KEYWORDS` | Never alert for these, e.g. `["sock", "tie"]` |
| `MAX_PRICE` | Only alert at or below this £ price |
| `ALERT_PRICE_DROPS` | Also alert when an outlet item gets cheaper |

Watching a size-filtered URL is the best way to cut noise — you'll only hear
about things you can actually buy in your size. Note the filter is applied at
alert time, so items you've filtered out are still recorded and won't alert
later if you widen the filters.

## Troubleshooting

- **"Got 0 items"** — Reiss (run on Next's platform) may be blocking GitHub's
  servers. Run it from your own computer instead, which uses a normal home
  connection. Nothing is overwritten when a run fails.
- **Too many alerts** — add a size filter to `SECTIONS`, or set `KEYWORDS`.
- **Reset** — delete `seen_items.json`; the next run becomes a fresh baseline.
