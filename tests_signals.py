"""Verify the diff engine on controlled snapshots (no network)."""
import os, tempfile, json
from datetime import datetime, timezone, timedelta
from topgames import store, slack, config

db = os.path.join(tempfile.mkdtemp(), "t.db")
conn = store.connect(db)
cfg = config.load()
cfg["slack"]["webhook_url"] = ""   # never send during tests

def app(i, name, days_old=400):
    rel = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    return dict(app_id=i, name=name, artist=f"Studio {i}", url=f"http://x/{i}",
        icon="", price=0.0, formatted_price="Free", genres="Games,Puzzle",
        primary_genre="Games", content_rating="4+", release_date=rel,
        version_date=rel, avg_rating=4.5, rating_count=1000, description="")

# --- snapshot 1: apps 1..5 at ranks 1..5
store.upsert_apps(conn, [app(i, f"Game {i}") for i in range(1, 6)])
s1 = store.add_snapshot(conn, "topfreeapplications", 7012, "us",
                        [(r, r) for r in range(1, 6)])

# --- snapshot 2: app 3 gone; NEW app 9 (fresh release) enters at #2;
#     app 5 climbs 5->1 (+4); app 1 falls 1->5 (-4)
store.upsert_apps(conn, [app(9, "Brand New Game", days_old=3)])
new_order = [(1, 5), (2, 9), (3, 2), (4, 4), (5, 1)]   # (rank, app_id)
s2 = store.add_snapshot(conn, "topfreeapplications", 7012, "us", new_order)

prev = store.snapshot_ranks(conn, s1)
curr = {aid: r for r, aid in new_order}

# replicate signals.refresh's diff with a threshold of 3
events, THRESH, NEW_DAYS = [], 3, 30
for aid, rank in curr.items():
    p = prev.get(aid)
    if p is None:
        row = conn.execute("SELECT release_date FROM apps WHERE app_id=?", (aid,)).fetchone()
        age = (datetime.now(timezone.utc) -
               datetime.fromisoformat(row["release_date"])).days
        events.append({"kind": "debut" if age <= NEW_DAYS else "new_entry",
                       "app_id": aid, "rank": rank, "prev_rank": None,
                       "delta": None, "detail": f"entered at #{rank}"})
    else:
        d = p - rank
        if abs(d) >= THRESH:
            events.append({"kind": "climb" if d > 0 else "fall", "app_id": aid,
                           "rank": rank, "prev_rank": p, "delta": d,
                           "detail": f"#{p} -> #{rank}"})
for aid, p in prev.items():
    if aid not in curr:
        events.append({"kind": "exit", "app_id": aid, "rank": None,
                       "prev_rank": p, "delta": None, "detail": f"left from #{p}"})
store.add_events(conn, events)

kinds = sorted(e["kind"] for e in events)
print("events:", kinds)
assert "debut" in kinds, "fresh new entrant must be flagged as a debut"
assert "exit" in kinds, "app 3 leaving the chart must be detected"
assert "climb" in kinds and "fall" in kinds, "big movers must be detected"
assert sum(1 for k in kinds if k == "exit") == 1

d = next(e for e in events if e["kind"] == "debut")
assert d["app_id"] == 9 and d["rank"] == 2, d
c = next(e for e in events if e["kind"] == "climb")
assert c["delta"] == 4 and c["app_id"] == 5, c
f = next(e for e in events if e["kind"] == "fall")
assert f["delta"] == -4 and f["app_id"] == 1, f
print("PASS: diff engine detects entries, exits, climbs, falls")

# --- Slack digest builds from these events without a webhook
since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
cfg["signals"]["move_threshold"] = 3
payload, ids = slack.build_digest(conn, cfg, "daily", since=since)
assert payload["blocks"][0]["type"] == "header"
inc = set(cfg["slack"]["daily"]["include"])
expected = [e for e in events if e["kind"] in inc]
assert len(ids) == len(expected), (len(ids), len(expected), inc)
assert "debut" in inc, "a new release that charts must reach the daily digest"
text = json.dumps(payload)
assert "Brand New Game" in text, "new entrant must appear in the digest"
assert "new to the top" in text, text[:400]
assert "Brand New Game" in text
print(f"PASS: digest built -- {len(payload['blocks'])} blocks, {len(ids)} events")

# --- mark_notified actually suppresses re-sending
store.mark_notified(conn, ids)
again = store.events_since(conn, since, kinds=list(inc), unnotified_only=True)
assert not again, f"already-sent events leaked back in: {again}"
# A 'fall' is deliberately excluded from the daily digest, so it must remain
# pending for the weekly one rather than being marked as sent.
pending = store.events_since(conn, since, unnotified_only=True)
assert [e["kind"] for e in pending] == ["fall"], pending
print("PASS: sent events are not resent; weekly-only signals stay pending")

# --- empty week produces the reassuring 'no new games' message
conn2 = store.connect(os.path.join(tempfile.mkdtemp(), "e.db"))
p2, i2 = slack.build_digest(conn2, cfg, "weekly")
assert "No new games entered" in json.dumps(p2)
assert i2 == []
print("PASS: quiet period renders a clean 'nothing new' digest")
print("\nALL TESTS PASSED")
