"""Block Kit digests, per slack_digest_spec.md.

Colour comes only from links, emoji, `code` spans and the primary button --
Block Kit offers nothing else. The rating dot is data: it encodes the rating
band, so it differs row to row rather than decorating every line the same way.

Section order is fixed: new releases, in/out, current top 10, movers, and --
weekly only -- publishers. Daily and weekly carry deliberately different
headers, icons and fallback text so the two are told apart at a glance in a
busy channel.
"""
from datetime import datetime, timedelta, timezone

from . import store, viewdata

MAX_BLOCKS = 50
SECTION_LIMIT = 2900          # Slack's ceiling is 3000; leave headroom.
FIELD_LIMIT = 1900            # Ceiling is 2000 per field.
DAILY_NEW_SHOWN = 12
WEEKLY_NEW_SHOWN = 15
LAUNCH_TODAY = "🚀"           # Marks a game that shipped today, not merely this window.
MAX_CHIPS = 3                 # Genre chips per release.
QUIET_MOVE = 3                # |delta| below this does not count as movement.
MOVERS_SHOWN = 5
OUT_SHOWN = 12
PUBS_SHOWN = 8

PERIOD = {
    "daily":  {"emoji": "📅", "label": "DAILY",  "icon": ":sunrise:"},
    "weekly": {"emoji": "🗓️", "label": "WEEKLY", "icon": ":bar_chart:"},
}


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


def _quote(lines):
    """Slack's only grouping device: a quote bar down the left of a run."""
    return "\n".join(f"> {ln}" for ln in lines)


def chips(r):
    """Genre labels as `code` spans -- the closest Block Kit has to a tag."""
    gs = r.get("genres") or []
    if isinstance(gs, str):
        gs = [g for g in gs.split(",") if g]
    return " ".join(f"`{g}`" for g in gs[:MAX_CHIPS])


def _mover_line(m):
    return (f"{delta_str(m['delta'])}  <{m['url']}|{m['name']}>"
            + (f"  → `#{m['rank']}`" if m.get("rank") else ""))


def _top10_lines(rows):
    # The rank sits inside backticks so Slack renders it monospaced and the
    # column stays aligned; padding with plain spaces would be collapsed.
    return [f"`{r['rank']:>2}` {delta_str(r['delta']):>3}  <{r['url']}|{r['name']}>  "
            f"{r['rating']:.2f}★ · {r['artist']}" for r in rows]


def _newrel_line(r):
    tag = chips(r)
    rank = f"  `TOP 100 #{r['rank']}`" if r.get("rank") else ""
    # The App Store link is the title itself; Android hangs off the end,
    # since it is a search rather than a resolved page.
    # Slack wants & escaped inside a link, and the Play search URL has one.
    play = (f"  ·  <{r['play_url'].replace('&', '&amp;')}|▶ Android>"
            if r.get("play_url") else "")
    return (f"{dot(r['rating'], r['ratings'])} *<{r['url']}|{r['name']}>*"
            + (f"   {tag}" if tag else "") + rank
            + f"\n>     {r['artist']} · {rating_str(r['rating'], r['ratings'])}{play}")


def _day_label(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%b %d").upper()
    except ValueError:
        return "EARLIER"


def recent_releases(rows, days, shown):
    """Releases inside the window, newest first. The window is strict.

    Apple publishes no new-release feed, so this is a discovery sweep and some
    days it surfaces one game. That is the honest answer, so a thin window
    stays thin rather than quietly reaching further back.
    """
    inside = [r for r in rows if (r.get("days_old") or 0) <= days]
    inside = sorted(inside, key=lambda r: (r.get("released") or "", r["rating"]),
                    reverse=True)
    return inside[:shown]


def launched_today(rows):
    return [r for r in rows if (r.get("days_old") or 0) == 0]


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


def release_blocks(rows, total, window_days):
    """The leading section: what shipped, grouped by day, with genre chips.

    Anything that launched *today* is called out in the subtitle and kept in
    its own group -- inside a 3- or 7-day window "new" otherwise blurs, and a
    same-day launch is the one thing worth reacting to immediately.
    """
    fresh = launched_today(rows)
    caption = f"*🆕 NEW RELEASES*  ·  _last {window_days} days_  ·  `{len(rows)} game{'' if len(rows) == 1 else 's'}`"
    if fresh:
        caption += (f"\n{LAUNCH_TODAY} *{len(fresh)} launched today*"
                    + ("" if len(fresh) == len(rows) else
                       f"  ·  _{len(rows) - len(fresh)} earlier in the window_"))
    blocks = [_section(caption)]

    # group_by_day merges thin days into ranges, which would fold today into
    # "AUG 19 - 24" and lose exactly the distinction we just drew.
    if fresh:
        blocks.append(_section(f"*{LAUNCH_TODAY} TODAY*\n" +
                               _quote(_newrel_line(r) for r in
                                      sorted(fresh, key=lambda r: -r["rating"]))))
    rest = [r for r in rows if (r.get("days_old") or 0) != 0]
    for label, items in group_by_day(rest):
        blocks.append(_section(f"*{label}*\n" +
                               _quote(_newrel_line(r) for r in items)))
    more = total - len(rows)
    if more > 0:
        blocks.append(_context(f"_…and {more} more in the last 30 days_"))
    return blocks


def in_out_blocks(entered, exited, period_label):
    """`In` carries each game's live rank; `out` is a plain comma list."""
    if not entered and not exited:
        return []
    blocks = [_section(f"*🔄 IN AND OUT*  ·  _{period_label}_")]
    if entered:
        rows = sorted(entered, key=lambda e: e.get("rank") or 999)
        blocks.append(_section(
            f"*In* `{len(entered)}`\n" + _quote(
                f"`#{e['rank']}`  <{e['url']}|{e['name']}> — {e['artist']}"
                for e in rows)))
    if exited:
        names = ", ".join(e["name"] for e in exited[:OUT_SHOWN])
        more = len(exited) - OUT_SHOWN
        if more > 0:
            names += f", …and {more} more"
        blocks.append(_section(f"*Out* `{len(exited)}`\n" + _quote([names])))
    return blocks


def mover_blocks(up, down, period_label):
    if not up and not down:
        return []
    blocks = [_section(f"*📊 MOVERS*  ·  _{period_label}_  ·  "
                       f"_{len(up)} up, {len(down)} down_")]
    if up:
        blocks.append(_section("*Climbing*\n" +
                               _quote(_mover_line(m) for m in up[:MOVERS_SHOWN])))
    if down:
        blocks.append(_section("*Falling*\n" +
                               _quote(_mover_line(m) for m in down[:MOVERS_SHOWN])))
    return blocks


def publisher_blocks(items):
    """Company first, then how many it has charting, then exactly which ranks.

    The old form led with a bare count and a net rank delta summed across a
    publisher's titles, which read as noise; the ranks themselves are the
    thing anyone actually wanted.
    """
    ranks = {}
    urls = {}
    for r in items:
        ranks.setdefault(r["artist"], []).append(r["rank"])
        urls.setdefault(r["artist"], r.get("artist_url"))
    pubs = [(a, sorted(rs)) for a, rs in ranks.items() if len(rs) > 1]
    pubs.sort(key=lambda p: (-len(p[1]), p[1][0]))
    if not pubs:
        return []
    lines = []
    for artist, rs in pubs[:PUBS_SHOWN]:
        name = f"<{urls[artist]}|{artist}>" if urls.get(artist) else artist
        lines.append(f"*{name}* — {len(rs)} games — "
                     + ", ".join(f"#{n}" for n in rs))
    return [_section("*🏢 PUBLISHERS IN THE TOP 100*\n" + _quote(lines))]


def _actions(cfg, new_count, weekly):
    dash = cfg["web"].get("pages_url") or cfg["web"].get("repo_url") or ""
    if not dash:
        return None
    els = [{"type": "button", "style": "primary",
            "text": {"type": "plain_text", "text": "Open dashboard"}, "url": dash}]
    if new_count:
        els.append({"type": "button",
                    "text": {"type": "plain_text", "text": "All new releases"},
                    "url": dash})
    if weekly:
        # The spec's action_id button needs a bot token and an interactivity
        # endpoint; an incoming webhook has neither, so this links out instead.
        els.append({"type": "button",
                    "text": {"type": "plain_text", "text": "Movers"}, "url": dash})
    return {"type": "actions", "elements": els[:5]}


def _entries_exits(conn, cfg, since):
    """Where each game ended the window, not every move it made inside it.

    Over a week a game can enter, drop out and enter again. Listing it under
    both headings reads as a data error, so only its latest event counts --
    which is also the one that says where it stands now.
    """
    events = store.events_since(conn, since,
                                kinds=["new_entry", "debut", "exit"])
    latest, seen = [], set()
    for e in events:                       # newest first
        if e["app_id"] in seen:
            continue
        seen.add(e["app_id"])
        latest.append(e)
    entered = [e for e in latest if e["kind"] != "exit"]
    exited = [e for e in latest if e["kind"] == "exit"]
    return entered, exited


def build(conn, cfg, period="daily"):
    """Return (payload, event_ids). payload is None when nothing should post."""
    view = viewdata.build(conn, cfg)
    if view is None:
        return None, []

    weekly = period == "weekly"
    style = PERIOD["weekly" if weekly else "daily"]
    window = timedelta(days=7 if weekly else 1)
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

    now = datetime.now()
    new_days = int(slack_cfg.get("new_days") or (7 if weekly else 3))
    shown = recent_releases(
        new_rel, new_days, WEEKLY_NEW_SHOWN if weekly else DAILY_NEW_SHOWN)
    fresh_today = launched_today(shown)
    # Repeated in the subtitle and the notification text: a same-day launch
    # should be visible without opening the message.
    today_tag = (f"  ·  {LAUNCH_TODAY} *{len(fresh_today)} launched today*"
                 if fresh_today else "")
    today_short = f" ({len(fresh_today)} today)" if fresh_today else ""
    top10 = view["items"][:10]
    period_label = "this week" if weekly else "vs yesterday"

    if weekly:
        first = now - timedelta(days=6)
        # "Aug 18-24" reads better than "Aug 18-Aug 24" when the week
        # does not straddle a month boundary.
        end = now.strftime("%d") if first.month == now.month else now.strftime("%b %d")
        title = (f"{style['emoji']} WEEKLY ROUNDUP · {scope} · "
                 f"{first.strftime('%b %d')}–{end}")
        sub = (f"_Week in review_  ·  `{cfg['chart']}`  ·  top {cfg['chart_size']}  ·  "
               f"*{len(shown)}* new releases{today_tag}  ·  "
               f"{len(entered)} in, {len(exited)} out")
        next_run = f'Monday {slack_cfg.get("time", "09:00")} {tz}'
        fallback = (f"[WEEKLY] {scope} — {len(shown)} new releases{today_short}, "
                    f"{len(entered)} in, {len(exited)} out")
    else:
        title = f"{style['emoji']} DAILY · {scope} · {now.strftime('%a, %b %d')}"
        sub = (f"_Since yesterday_  ·  `{cfg['chart']}`  ·  top {cfg['chart_size']}  ·  "
               f"new releases across all genres{today_tag}")
        next_run = f'tomorrow {slack_cfg.get("time", "09:00")} {tz}'
        fallback = (f"[DAILY] {scope} — {len(shown)} new{today_short}, "
                    f"{len(up)} up, {len(down)} down, {len(entered)} in")

    # A day with nothing at all to say still posts: silence is
    # indistinguishable from a broken schedule.
    real_movement = [m for m in movers if abs(m["delta"]) >= QUIET_MOVE]
    if not weekly and not real_movement and not entered and not shown:
        link = f" <{dash}|Open>" if dash else ""
        return {
            "username": cfg["slack"].get("username") or "top_games",
            "icon_emoji": slack_cfg.get("icon_emoji") or style["icon"],
            "text": f"[DAILY] {scope} — chart unchanged",
            "blocks": [_context(
                f"{style['emoji']} *DAILY* · {scope} · {now.strftime('%a, %b %d')} — "
                f"chart unchanged, no new entries or releases.{link}")],
        }, event_ids

    blocks = [
        {"type": "header",
         "text": {"type": "plain_text", "text": title[:150], "emoji": True}},
        _context(sub),
    ]
    if shown:
        blocks += [{"type": "divider"}]
        blocks += release_blocks(shown, len(new_rel), new_days)

    io = in_out_blocks(entered, exited, "this week" if weekly else "since yesterday")
    if io:
        blocks += [{"type": "divider"}] + io

    blocks += [{"type": "divider"},
               _section("*🏆 CURRENT TOP 10*" + ("  ·  _7-day change_" if weekly else "")),
               _two_column(_top10_lines(top10))]

    mv = mover_blocks(up, down, "7 days" if weekly else "vs yesterday")
    if mv:
        blocks += [{"type": "divider"}] + mv

    if weekly:
        pubs = publisher_blocks(view["items"])
        if pubs:
            blocks += [{"type": "divider"}] + pubs

    act = _actions(cfg, len(new_rel), weekly)
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
        "icon_emoji": slack_cfg.get("icon_emoji") or style["icon"],
        "text": fallback,
        "blocks": blocks,
    }, event_ids
