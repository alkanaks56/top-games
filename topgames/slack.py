"""Slack Incoming Webhook delivery and Block Kit digest composition."""
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from . import store
from .signals import KIND_LABELS

EMOJI = {"new_entry": ":new:", "debut": ":rocket:", "exit": ":arrow_down_small:",
         "climb": ":chart_with_upwards_trend:", "fall": ":chart_with_downwards_trend:",
         "new_release": ":sparkles:"}
SLACK_TEXT_LIMIT = 2900  # Block Kit section limit is 3000; leave headroom.


class SlackError(RuntimeError):
    pass


def post(webhook_url, payload, timeout=15):
    if not webhook_url:
        raise SlackError(
            "No Slack webhook configured. Add slack.webhook_url to config.json.")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "top-games/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8").strip()
            if text != "ok":
                raise SlackError(f"Slack replied {resp.status}: {text}")
            return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        hint = ""
        if exc.code == 404:
            hint = " -- the webhook URL looks wrong or was revoked."
        elif exc.code == 403:
            hint = " -- the app may have been removed from the channel."
        raise SlackError(f"Slack rejected the message ({exc.code} {detail}){hint}")
    except urllib.error.URLError as exc:
        raise SlackError(f"Could not reach Slack: {exc.reason}")


def _stars(rating):
    if not rating:
        return "unrated"
    return f"{rating:.2f}★"


def _line(ev):
    """One markdown line describing an event."""
    name = ev.get("name") or f"app {ev['app_id']}"
    url = ev.get("url") or ""
    title = f"<{url}|{name}>" if url else f"*{name}*"
    artist = ev.get("artist") or ""
    bits = []
    if ev["kind"] in ("new_entry", "debut"):
        bits.append(f"entered at *#{ev['rank']}*")
    elif ev["kind"] == "climb":
        bits.append(f"*#{ev['prev_rank']} → #{ev['rank']}* (+{ev['delta']})")
    elif ev["kind"] == "fall":
        bits.append(f"*#{ev['prev_rank']} → #{ev['rank']}* ({ev['delta']})")
    elif ev["kind"] == "exit":
        bits.append(f"left from *#{ev['prev_rank']}*")
    elif ev["kind"] == "new_release":
        rel = (ev.get("release_date") or "")[:10]
        bits.append(f"released {rel}" if rel else "new release")
    rating = ev.get("avg_rating") or 0
    count = ev.get("rating_count") or 0
    if count:
        bits.append(f"{_stars(rating)} ({count:,})")
    tail = " · ".join(bits)
    return f"{EMOJI.get(ev['kind'],'•')} {title} — {artist}\n     {tail}"


def _section(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:SLACK_TEXT_LIMIT]}}


def _group(events, kind, limit):
    picked = [e for e in events if e["kind"] == kind]
    if kind in ("new_entry", "debut"):
        picked.sort(key=lambda e: e["rank"] or 999)
    elif kind == "climb":
        picked.sort(key=lambda e: -(e["delta"] or 0))
    elif kind == "fall":
        picked.sort(key=lambda e: (e["delta"] or 0))
    return picked[:limit], max(0, len(picked) - limit)


def build_digest(conn, cfg, period="daily", since=None):
    """Compose the Block Kit payload for a digest. Returns (payload, event_ids)."""
    slack_cfg = cfg["slack"][period]
    sig = cfg["signals"]
    limit = sig["max_items_per_section"]
    window = timedelta(days=1 if period == "daily" else 7)
    since = since or (datetime.now(timezone.utc) - window).isoformat(timespec="seconds")

    kinds = slack_cfg["include"]
    events = store.events_since(conn, since, kinds=kinds)
    event_ids = [e["id"] for e in events]

    genre = cfg["genre"].replace("_", " ").title()
    country = cfg["country"].upper()
    label = "Daily" if period == "daily" else "Weekly"
    stamp = datetime.now().strftime("%b %d, %Y")

    blocks = [
        {"type": "header", "text": {"type": "plain_text",
         "text": f"{label} {genre} Games Report — {country}", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
         "text": f"{stamp} · chart: `{cfg['chart']}` · top {cfg['chart_size']}"}]},
    ]

    # Headline counters so the channel gets the answer without reading the list.
    entered = [e for e in events if e["kind"] in ("new_entry", "debut")]
    released = [e for e in events if e["kind"] == "new_release"]
    if entered or released:
        summary = []
        if entered:
            summary.append(f"*{len(entered)}* new to the top {cfg['chart_size']}")
        if released:
            summary.append(f"*{len(released)}* newly released")
        blocks.append(_section(" · ".join(summary)))
    else:
        blocks.append(_section(
            f":white_check_mark: No new games entered the top {cfg['chart_size']} "
            f"this {'day' if period=='daily' else 'week'}."))

    order = ["debut", "new_entry", "new_release", "climb", "fall", "exit"]
    for kind in order:
        if kind not in kinds:
            continue
        picked, extra = _group(events, kind, limit)
        if not picked:
            continue
        blocks.append({"type": "divider"})
        heading = f"*{KIND_LABELS[kind]}*  ({len(picked) + extra})"
        body = "\n".join(_line(e) for e in picked)
        if extra:
            body += f"\n_…and {extra} more_"
        blocks.append(_section(f"{heading}\n{body}"))

    if period == "weekly" and cfg["slack"]["weekly"].get("show_full_chart"):
        snap, rows = store.latest_chart(conn, cfg["chart"])
        if rows:
            top = rows[:10]
            body = "\n".join(
                f"`{r['rank']:>3}` <{r['url']}|{r['name']}> — {_stars(r['avg_rating'])}"
                for r in top)
            blocks.append({"type": "divider"})
            blocks.append(_section(f"*Current top 10*\n{body}"))

    blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
        "text": "Source: Apple App Store (iTunes RSS + Search API) · "
                "generated by top_games"}]})

    payload = {
        "username": cfg["slack"].get("username") or "Top Games Bot",
        "icon_emoji": cfg["slack"].get("icon_emoji") or ":jigsaw:",
        "text": f"{label} {genre} games report: {len(entered)} new to chart, "
                f"{len(released)} new releases",  # notification fallback text
        "blocks": blocks,
    }
    return payload, event_ids


def build_realtime_alert(cfg, events):
    """A compact 'a new game just entered the chart' alert."""
    genre = cfg["genre"].replace("_", " ").title()
    lines = "\n".join(_line(e) for e in events[:10])
    return {
        "username": cfg["slack"].get("username") or "Top Games Bot",
        "icon_emoji": cfg["slack"].get("icon_emoji") or ":jigsaw:",
        "text": f"{len(events)} new game(s) entered the {genre} top {cfg['chart_size']}",
        "blocks": [
            _section(f":rotating_light: *New in the {genre} top "
                     f"{cfg['chart_size']} ({cfg['country'].upper()})*\n{lines}"),
        ],
    }


def test_message(cfg):
    return {
        "username": cfg["slack"].get("username") or "Top Games Bot",
        "icon_emoji": cfg["slack"].get("icon_emoji") or ":jigsaw:",
        "text": "top_games connection test",
        "blocks": [_section(
            ":white_check_mark: *top_games is connected.*\n"
            f"Tracking `{cfg['chart']}` · {cfg['genre']} · "
            f"{cfg['country'].upper()} · top {cfg['chart_size']}.")],
    }
