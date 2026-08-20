"""Block Kit digests, per slack_digest_spec.md.

Colour comes only from links, emoji, `code` spans and the primary button --
Block Kit offers nothing else. The rating dot is data: it encodes the rating
band, so it differs row to row rather than decorating every line the same way.
"""
from datetime import datetime, timedelta, timezone

from . import store, viewdata

MAX_BLOCKS = 50
SECTION_LIMIT = 2900          # Slack's ceiling is 3000; leave headroom.
FIELD_LIMIT = 1900            # Ceiling is 2000 per field.
DAILY_NEW_SHOWN = 8
WEEKLY_NEW_SHOWN = 8
QUIET_MOVE = 3                # |delta| below this does not count as movement.


def dot(rating, count):
    if not count:
        return "⚪"
    if rating >= 4.7:
        return "🟢"
    if rating >= 4.0:
        return "🟡"
    return "🔴"


def rating_str(rating, count):
    return f"{rating:.2f}★ ({count:,})" if count else "no ratings yet"


def delta_str(d):
    if d is None:
        return "—"
    if d > 0:
        return f"▲{d}"
    if d < 0:
        return f"▼{abs(d)}"
    return "—"


def _section(text):
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:SECTION_LIMIT]}}


def _context(text):
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text[:SECTION_LIMIT]}]}


def _mover_line(m):
    return f"{delta_str(m['delta'])} <{m['url']}|{m['name']}>"


def _top10_lines(rows):
    # The rank sits inside backticks so Slack renders it monospaced and the
    # column stays aligned; padding with plain spaces would be collapsed.
    return [f"`{r['rank']:>2}` {delta_str(r['delta']):>3}  <{r['url']}|{r['name']}>  "
            f"{r['rating']:.2f}★ · {r['artist']}" for r in rows]


def _newrel_line(r):
    return (f"{dot(r['rating'], r['ratings'])} <{r['url']}|{r['name']}>  "
            f"{r['artist']} · {rating_str(r['rating'], r['ratings'])}"
            + (f"  `TOP 100 #{r['rank']}`" if r.get("rank") else ""))


def _day_label(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%b %d").upper()
    except ValueError:
        return "EARLIER"


def group_by_day(rows):
    """Group releases by date, newest first.

    A day carrying three or more items stands alone. Thinner days merge with
    their neighbours, but only until the merged group itself reaches three --
    otherwise a fortnight of quiet days collapses into one meaningless range.
    """
    buckets = {}
    for r in rows:
        buckets.setdefault(r["released"], []).append(r)
    days = sorted(buckets, reverse=True)

    out, i = [], 0
    while i < len(days):
        if len(buckets[days[i]]) >= 3:
            out.append((_day_label(days[i]),
                        sorted(buckets[days[i]], key=lambda r: -r["rating"])))
            i += 1
            continue
        j, merged = i, []
        while j < len(days) and len(buckets[days[j]]) < 3 and len(merged) < 3:
            merged += buckets[days[j]]
            j += 1
        newest, oldest = _day_label(days[i]), _day_label(days[j - 1])
        if newest == oldest:
            label = newest
        elif newest.split()[0] == oldest.split()[0]:      # same month
            label = f"{oldest} – {newest.split()[1]}"
        else:
            label = f"{oldest} – {newest}"
        out.append((label, sorted(merged, key=lambda r: -r["rating"])))
        i = j
    return out


def _two_column(lines):
    """Top 10 as two side-by-side fields, as the spec lays it out."""
    half = (len(lines) + 1) // 2
    left, right = lines[:half], lines[half:]
    fields = [{"type": "mrkdwn", "text": "\n".join(left)[:FIELD_LIMIT]}]
    if right:
        fields.append({"type": "mrkdwn", "text": "\n".join(right)[:FIELD_LIMIT]})
    return {"type": "section", "fields": fields}


def _actions(cfg, new_count, weekly):
    dash = cfg["web"].get("pages_url") or cfg["web"].get("repo_url") or ""
    if not dash:
        return None
    els = [{"type": "button", "style": "primary",
            "text": {"type": "plain_text", "text": "Open dashboard"}, "url": dash}]
    if new_count:
        els.append({"type": "button",
                    "text": {"type": "plain_text", "text": f"All {new_count} new releases"},
                    "url": dash})
    if weekly:
        # The spec's action_id button needs a bot token and an interactivity
        # endpoint; an incoming webhook has neither, so this links out instead.
        els.append({"type": "button",
                    "text": {"type": "plain_text", "text": "Movers"}, "url": dash})
    return {"type": "actions", "elements": els[:5]}


def _entries_exits(conn, cfg, since):
    entered = store.events_since(conn, since, kinds=["new_entry", "debut"])
    exited = store.events_since(conn, since, kinds=["exit"])
    return entered, exited


def build(conn, cfg, period="daily"):
    """Return (payload, event_ids). payload is None when nothing should post."""
    view = viewdata.build(conn, cfg)
    if view is None:
        return None, []

    window = timedelta(days=1 if period == "daily" else 7)
    since = (datetime.now(timezone.utc) - window).isoformat(timespec="seconds")
    slack_cfg = cfg["slack"][period]

    genre = cfg["genre"].replace("_", " ").title()
    country = cfg["country"].upper()
    scope = f"{genre} · {country}"
    dash = cfg["web"].get("pages_url") or cfg["web"].get("repo_url") or ""
    tz = cfg["slack"].get("timezone", "UTC")

    movers = view["movers"]
    up = sorted([m for m in movers if m["delta"] > 0], key=lambda m: -m["delta"])
    down = sorted([m for m in movers if m["delta"] < 0], key=lambda m: m["delta"])
    entered, exited = _entries_exits(conn, cfg, since)
    new_rel = view["new_releases"]
    event_ids = [e["id"] for e in entered + exited]

    stamp = datetime.now().strftime("%b %d, %Y")
    top10 = view["items"][:10]

    if period == "daily":
        # A day with nothing to say still posts: silence is indistinguishable
        # from a broken schedule.
        real_movement = [m for m in movers if abs(m["delta"]) >= QUIET_MOVE]
        if not real_movement and not entered:
            link = f" <{dash}|Open>" if dash else ""
            return {
                "username": cfg["slack"].get("username") or "top_games",
                "icon_emoji": cfg["slack"].get("icon_emoji") or ":jigsaw:",
                "text": f"{scope} daily — chart unchanged",
                "blocks": [_context(
                    f"{scope} — daily · {stamp} · chart unchanged, "
                    f"no new entries.{link}")],
            }, event_ids

        blocks = [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"{scope} — daily chart digest"[:150]}},
            _context(f"{stamp}  ·  `{cfg['chart']}`  ·  top {cfg['chart_size']}"
                     f"  ·  {len(new_rel)} new since last run"),
        ]
        if up or down:
            line = "   ".join(_mover_line(m) for m in (up[:5] + down[:5]))
            blocks.append(_section(
                f"*Movers*  _vs {'yesterday' if view['span_days'] <= 1 else 'last run'}_\n"
                f"{line}  ·  _{len(up)} up, {len(down)} down_"))
        blocks += [{"type": "divider"},
                   _section(f"*Current top 10*"),
                   _two_column(_top10_lines(top10))]
        if entered:
            blocks += [{"type": "divider"}, _section(
                "*New to the chart*\n" + "\n".join(
                    f"▲ <{e['url']}|{e['name']}>  entered at #{e['rank']} · {e['artist']}"
                    for e in entered[:8]))]
        shown = sorted(new_rel, key=lambda r: -r["rating"])[:DAILY_NEW_SHOWN]
        if shown:
            blocks += [{"type": "divider"}, _section(
                f"*New releases*  `{len(new_rel)} · showing {len(shown)} highest rated`")]
            for label, items in group_by_day(shown):
                blocks.append(_section(f"*{label}*\n" +
                                       "\n".join(_newrel_line(r) for r in items)))
            rest = len(new_rel) - len(shown)
            if rest:
                blocks.append(_context(f"_…and {rest} more_"))
        fallback = (f"{scope} daily — {len(up)} up, {len(down)} down, "
                    f"{len(entered)} new")
        next_run = f'tomorrow {cfg["slack"]["daily"].get("time","09:00")} {tz}'
    else:
        start = (datetime.now() - timedelta(days=6)).strftime("%b %d")
        blocks = [
            {"type": "header", "text": {"type": "plain_text",
             "text": f"{scope} — week of {start}–{datetime.now().strftime('%b %d')}"[:150]}},
            _context(f"`{cfg['chart']}`  ·  top {cfg['chart_size']}  ·  "
                     f"*{len(new_rel)}* new releases  ·  "
                     f"{len(entered)} in, {len(exited)} out"),
        ]
        if up or down:
            blocks.append(_section("*Movers*  _7 days_\n" +
                "   ".join(_mover_line(m) for m in (up[:5] + down[:5]))))
        blocks += [{"type": "divider"}, _section("*Top 10*  _7-day change_"),
                   _two_column(_top10_lines(top10))]
        if entered:
            blocks += [{"type": "divider"}, _section("*In*\n" + "\n".join(
                f"▲ <{e['url']}|{e['name']}>  entered at #{e['rank']} · {e['artist']}"
                for e in entered[:8]))]
        if exited:
            blocks.append(_section("*Out*\n" + "\n".join(
                f"▼ <{e['url']}|{e['name']}>  was #{e['prev_rank']} · {e['artist']}"
                for e in exited[:8])))
        shown = sorted(new_rel, key=lambda r: -r["rating"])[:WEEKLY_NEW_SHOWN]
        if shown:
            blocks += [{"type": "divider"}, _section(
                f"*New releases*  `{len(new_rel)} · showing {len(shown)} highest rated`")]
            for label, items in group_by_day(shown):
                blocks.append(_section(f"*{label}*\n" +
                                       "\n".join(_newrel_line(r) for r in items)))
            rest = len(new_rel) - len(shown)
            if rest:
                blocks.append(_context(f"_…and {rest} more_"))
        pubs = [p for p in view["publishers"] if p["titles"] > 1][:8]
        if pubs:
            blocks += [{"type": "divider"}, _section(
                "*Publishers in the top 100*\n" + "\n".join(
                    f"`{p['titles']:>2}` {delta_str(p['net_delta']):>3}  {p['artist']}"
                    for p in pubs))]
        fallback = (f"{scope} weekly — {len(new_rel)} new releases, "
                    f"{len(entered)} chart entries")
        next_run = f'Monday {cfg["slack"]["weekly"].get("time","09:00")} {tz}'

    act = _actions(cfg, len(new_rel), period == "weekly")
    if act:
        blocks.append(act)
    blocks.append(_context(
        f"Apple App Store · iTunes RSS + Search API · next run {next_run}"))

    if len(blocks) > MAX_BLOCKS:
        blocks = blocks[:MAX_BLOCKS - 1] + [_context("_truncated to fit Slack's block limit_")]

    mention = cfg["slack"].get("mention") or ""
    if mention:
        blocks.insert(2, _section(mention))

    return {
        "username": cfg["slack"].get("username") or "top_games",
        "icon_emoji": cfg["slack"].get("icon_emoji") or ":jigsaw:",
        "text": fallback,
        "blocks": blocks,
    }, event_ids
