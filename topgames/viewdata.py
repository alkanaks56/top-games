"""Derive the figures the dashboard shows from stored snapshots.

Kept apart from rendering so the numbers can be checked on their own.
"""
import statistics
from datetime import datetime, timedelta, timezone

from . import store

HISTORY_POINTS = 12


def _parse(iso):
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _genre_label(genres):
    """'Games,Board,Puzzle,Entertainment' -> 'Board / Puzzle'."""
    parts = [g for g in (genres or "").split(",") if g and g != "Games"]
    return " / ".join(parts[:2]) or "Puzzle"


def comparison_snapshot(conn, chart, target_days=7):
    """Newest snapshot at least `target_days` old, else the oldest we hold.

    Returns (snapshot_row, actual_days_apart). A brand-new database has only
    today's data, so the dashboard labels the delta column with the span it
    could actually measure rather than claiming a 7-day change it cannot see.
    """
    snaps = conn.execute(
        "SELECT * FROM snapshots WHERE chart=? ORDER BY id DESC", (chart,)).fetchall()
    if len(snaps) < 2:
        return None, 0
    newest = _parse(snaps[0]["captured_at"])
    for row in snaps[1:]:
        when = _parse(row["captured_at"])
        if when and newest and (newest - when).days >= target_days:
            return row, (newest - when).days
    oldest = snaps[-1]
    when = _parse(oldest["captured_at"])
    days = (newest - when).days if (when and newest) else 0
    return oldest, days


def build(conn, cfg):
    """Assemble every figure the page renders."""
    chart = cfg["chart"]
    snap, rows = store.latest_chart(conn, chart)
    if not snap:
        return None

    base, span_days = comparison_snapshot(conn, chart, target_days=7)
    base_ranks = store.snapshot_ranks(conn, base["id"]) if base else {}

    # Rank history for the sparkline, covering exactly the period the delta
    # describes. Taking merely the newest N snapshots let the comparison point
    # fall outside the window, so a game could report a rank change while its
    # line sat perfectly flat.
    all_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM snapshots WHERE chart=? ORDER BY id", (chart,))]
    start = all_ids.index(base["id"]) if base and base["id"] in all_ids else 0
    window = all_ids[start:]
    if len(window) > HISTORY_POINTS:
        # Thin the run evenly, always keeping the first and last points so the
        # ends still line up with the reported delta.
        step = (len(window) - 1) / (HISTORY_POINTS - 1)
        window = [window[round(i * step)] for i in range(HISTORY_POINTS)]
    order = {sid: i for i, sid in enumerate(window)}

    history = {}
    if window:
        rows_h = conn.execute(
            "SELECT snapshot_id, app_id, rank FROM ranks WHERE snapshot_id IN (%s)"
            % ",".join("?" * len(window)), window).fetchall()
        buckets = {}
        for r in rows_h:
            buckets.setdefault(r["app_id"], []).append(
                (order[r["snapshot_id"]], r["rank"]))
        history = {aid: [rank for _, rank in sorted(pairs)]
                   for aid, pairs in buckets.items()}

    publisher_counts = {}
    for r in rows:
        publisher_counts[r["artist"]] = publisher_counts.get(r["artist"], 0) + 1

    new_days = cfg["signals"]["new_release_days"]
    now = datetime.now(timezone.utc)
    items = []
    for r in rows:
        prev = base_ranks.get(r["app_id"])
        delta = (prev - r["rank"]) if prev is not None else None
        released = _parse(r.get("release_date"))
        age_days = (now - released).days if released else None
        items.append({
            "rank": r["rank"],
            "app_id": r["app_id"],
            "name": r["name"],
            "artist": r["artist"] or "Unknown",
            "url": r["url"],
            "icon": r["icon"],
            "genre": _genre_label(r["genres"]),
            "rating": round(r["avg_rating"] or 0, 2),
            "ratings": r["rating_count"] or 0,
            "released": (r.get("release_date") or "")[:10],
            "price": r["formatted_price"] or "Free",
            "delta": delta,
            "prev_rank": prev,
            "history": history.get(r["app_id"], []),
            "artist_url": r.get("artist_url") or "",
            "titles_charting": publisher_counts.get(r["artist"], 1),
            "is_new_release": age_days is not None and age_days <= new_days,
            "is_new_entry": prev is None and bool(base_ranks),
        })

    ratings = [i["rating"] for i in items if i["rating"]]
    climbing = sum(1 for i in items if (i["delta"] or 0) > 0)
    falling = sum(1 for i in items if (i["delta"] or 0) < 0)

    publishers = {}
    for i in items:
        p = publishers.setdefault(i["artist"], {
            "artist": i["artist"], "artist_url": i["artist_url"], "titles": 0,
            "best_rank": 999, "ratings_total": 0, "rating_sum": 0.0, "net_delta": 0})
        p["titles"] += 1
        p["best_rank"] = min(p["best_rank"], i["rank"])
        p["ratings_total"] += i["ratings"]
        p["rating_sum"] += i["rating"]
        p["net_delta"] += i["delta"] or 0
    for p in publishers.values():
        p["avg_rating"] = round(p["rating_sum"] / p["titles"], 2)
        del p["rating_sum"]
    publisher_list = sorted(publishers.values(),
                            key=lambda p: (-p["titles"], p["best_rank"]))

    movers = sorted([i for i in items if i["delta"]],
                    key=lambda i: -abs(i["delta"]))[:12]

    # New releases are drawn from the whole tracked genre, not just the chart.
    # Restricting them to charting titles is why this list looked almost empty:
    # very few brand-new games reach the top 100 in their first month.
    charted = {i["app_id"]: i["rank"] for i in items}
    cutoff = (now - timedelta(days=new_days)).isoformat()
    genre_name = cfg["genre"].replace("_", " ").title()
    fresh_rows = conn.execute("""
        SELECT * FROM apps WHERE release_date >= ? AND genres LIKE ?
        ORDER BY release_date DESC LIMIT 300
    """, (cutoff, f"%{genre_name}%")).fetchall()
    new_releases = []
    for r in fresh_rows:
        released = _parse(r["release_date"])
        new_releases.append({
            "app_id": r["app_id"], "name": r["name"],
            "artist": r["artist"] or "Unknown", "url": r["url"] or "",
            "artist_url": r["artist_url"] or "", "icon": r["icon"] or "",
            "genre": _genre_label(r["genres"]),
            "rating": round(r["avg_rating"] or 0, 2),
            "ratings": r["rating_count"] or 0,
            "released": (r["release_date"] or "")[:10],
            "days_old": (now - released).days if released else None,
            "rank": charted.get(r["app_id"]),
        })

    return {
        "captured_at": snap["captured_at"],
        "span_days": span_days,
        "items": items,
        "movers": movers,
        "new_releases": new_releases,
        "publishers": publisher_list,
        "stats": {
            "tracked": len(items),
            "climbing": climbing,
            "falling": falling,
            "median_rating": round(statistics.median(ratings), 2) if ratings else 0,
            "publishers": len(publishers),
            "new_releases": len(new_releases),
        },
    }
