"""Command line entry point."""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from . import (config, digest as digest_mod, signals, slack, sources,
               staticgen, store, viewdata, web)
from .scheduler import install_launchd, uninstall_launchd, schedule_status


def cmd_init(args, cfg):
    path = config.CONFIG_PATH
    if os.path.exists(path) and not args.force:
        print(f"{path} already exists (use --force to overwrite).")
    else:
        with open(path, "w") as fh:
            json.dump(config.DEFAULTS, fh, indent=2)
        print(f"Wrote {path}")
    config.save_example()
    store.connect()
    print("Database ready at data/topgames.db")
    print("\nNext: paste your Slack webhook URL into config.json "
          "(slack.webhook_url), then run:  python3 -m topgames refresh")
    return 0


def _view_path(d):
    return os.path.join(config.ROOT, "data", f"{d['slug']}.view.json")


def _fetch_snapshot(d):
    """Fetch and shape a chart-only dataset. Two requests, nothing persisted."""
    entries = sources.fetch_chart(d["country"], d["chart"],
                                  d["genre_id"], d["chart_size"])
    meta = sources.lookup([a for _, a in entries], d["country"])
    return viewdata.build_snapshot(entries, meta, d)


def _refresh_one(d):
    """Refresh a single dataset. Chart-only datasets keep no history."""
    if not d["history"]:
        view = _fetch_snapshot(d)
        # refresh and export run as separate processes, so hand the fetched
        # chart over on disk rather than re-requesting it minutes later.
        os.makedirs(os.path.dirname(_view_path(d)), exist_ok=True)
        with open(_view_path(d), "w") as fh:
            json.dump(view, fh, default=str)
        return {"chart_size": len(entries_count(view)), "baseline": False,
                "events": 0, "new_entries": 0, "exits": 0, "movers": 0,
                "new_releases": len(view["new_releases"]), "chart_only": True}
    conn = store.connect(d["db_path"])
    try:
        return signals.refresh(conn, d, verbose=False)
    finally:
        conn.close()


def entries_count(view):
    return view["items"]


def cmd_refresh(args, cfg):
    """Refresh every configured dataset, isolating failures."""
    ds = config.datasets(cfg)
    failed = []
    for d in ds:
        tag = f"{d['slug']}{' (chart only)' if not d['history'] else ''}"
        try:
            s = _refresh_one(d)
            print(f"  {tag:26} {s['chart_size']:>3} ranked · "
                  f"{s['new_entries']} new · {s['movers']} movers · "
                  f"{s['new_releases']} releases")
        except Exception as exc:
            failed.append((d["slug"], exc))
            print(f"  {tag:26} FAILED: {exc}", file=sys.stderr)
    if failed:
        print(f"\n{len(failed)} of {len(ds)} datasets failed", file=sys.stderr)
        return 1
    return 0


def _cmd_refresh_primary(args, cfg):
    conn = store.connect()
    summary = signals.refresh(conn, cfg)
    print(f"\nSnapshot #{summary['snapshot_id']}: {summary['chart_size']} ranked apps, "
          f"{summary['genre_pool']} apps in genre pool")
    print(f"  new in chart : {summary['new_entries']}")
    print(f"  dropped out  : {summary['exits']}")
    print(f"  big movers   : {summary['movers']}")
    print(f"  new releases : {summary['new_releases']}")

    # Optional immediate alert when something enters the chart.
    if cfg["slack"].get("realtime_new_entry") and not summary["baseline"]:
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        fresh = store.events_since(conn, since, kinds=["new_entry", "debut"],
                                   unnotified_only=True)
        if fresh:
            try:
                slack.post(cfg["slack"]["webhook_url"],
                           slack.build_realtime_alert(cfg, fresh))
                store.mark_notified(conn, [e["id"] for e in fresh])
                print(f"  posted realtime alert for {len(fresh)} new entries")
            except slack.SlackError as exc:
                print(f"  slack alert failed: {exc}", file=sys.stderr)
    conn.close()
    return 0


def cmd_digest(args, cfg):
    conn = store.connect(config.primary(cfg)["db_path"])
    payload, ids = digest_mod.build(conn, config.primary(cfg), args.period)
    if payload is None:
        print(f"Nothing to report and skip_if_empty is on -- no {args.period} digest sent.")
        return 0
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        print(f"\n(dry run -- {len(ids)} signals would be marked as notified)",
              file=sys.stderr)
        return 0
    try:
        slack.post(cfg["slack"]["webhook_url"], payload)
    except slack.SlackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    store.mark_notified(conn, ids)
    print(f"Sent {args.period} digest covering {len(ids)} signals.")
    conn.close()
    return 0


def cmd_run(args, cfg):
    """Refresh then send -- the single command a scheduled job calls."""
    rc = cmd_refresh(args, cfg)
    if rc:
        return rc
    return cmd_digest(args, cfg)


def cmd_slack_test(args, cfg):
    try:
        slack.post(cfg["slack"]["webhook_url"], slack.test_message(cfg))
    except slack.SlackError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Test message sent.")
    return 0


def cmd_serve(args, cfg):
    web.serve(cfg, args.host, args.port)
    return 0


def cmd_chart(args, cfg):
    cfg = config.primary(cfg)
    conn = store.connect(cfg["db_path"])
    snap, rows = store.latest_chart(conn, cfg["chart"])
    if not snap:
        print("No data yet -- run:  python3 -m topgames refresh")
        return 1
    print(f"{cfg['chart']} / {cfg['genre']} / {cfg['country'].upper()} "
          f"@ {snap['captured_at']}\n")
    for r in rows[:args.limit]:
        rating = f"{r['avg_rating']:.2f}★" if r["avg_rating"] else "  —  "
        print(f"{r['rank']:>3}. {r['name'][:44]:44} {rating:>7} "
              f"{r['rating_count']:>9,}  {r['artist'][:26]}")
    conn.close()
    return 0


def cmd_export(args, cfg):
    """Publish every dataset into its own subtree, plus a root index."""
    ds = config.datasets(cfg)
    listing = [{"country": d["country"], "genre": d["genre"], "slug": d["slug"],
                "path": d["outdir_rel"],
                "title": f"{d['genre'].replace('_',' ').title()} · {d['country'].upper()}",
                "primary": d["primary"]} for d in ds]
    outdir = getattr(args, "outdir", "site") or "site"
    entries, failed = [], []

    for d in ds:
        try:
            view = None
            if not d["history"]:
                path = _view_path(d)
                if os.path.exists(path):
                    with open(path) as fh:
                        view = json.load(fh)
                else:
                    view = _fetch_snapshot(d)
            conn = store.connect(d["db_path"]) if d["history"] else None
            try:
                sub = os.path.join(outdir, d["outdir_rel"])
                res = staticgen.build(conn, d, sub, view=view, datasets=listing)
                if d["primary"]:
                    # Keep the legacy root paths alive for the deployed Worker.
                    staticgen.build(conn, d, outdir, view=view, datasets=listing)
                meta = next(x for x in listing if x["slug"] == d["slug"])
                v = view if view is not None else viewdata.build(conn, d)
                entries.append(dict(meta, captured_at=v["captured_at"],
                                    tracked=v["stats"]["tracked"],
                                    top3=[i["name"] for i in v["items"][:3]]))
                print(f"  {d['slug']:26} {res['chart_rows']:>3} rows -> {sub}")
            finally:
                if conn:
                    conn.close()
        except Exception as exc:
            failed.append(d["slug"])
            print(f"  {d['slug']:26} FAILED: {exc}", file=sys.stderr)

    if entries:
        # No landing page: the root IS the primary dashboard, and country and
        # genre are filters inside it like every other filter.
        staticgen.write_manifest(entries, outdir)
        print(f"  manifest -> {outdir}/manifest.json ({len(entries)} datasets)")
    return 1 if failed else 0


def _cmd_export_single(args, cfg):
    conn = store.connect()
    if args.prune:
        print("pruned:", store.prune(conn))
    result = staticgen.build(conn, cfg, args.outdir)
    print(f"Wrote {result['outdir']}/ -- {result['chart_rows']} chart rows, "
          f"{result['new']} new releases, {result['events']} signals")
    print("Slack payloads:", ", ".join(result["slack_payloads"]))
    conn.close()
    return 0


def cmd_schedule(args, cfg):
    if args.action == "install":
        return install_launchd(cfg)
    if args.action == "uninstall":
        return uninstall_launchd()
    return schedule_status()


def build_parser():
    p = argparse.ArgumentParser(
        prog="topgames",
        description="Track App Store puzzle-game charts and push digests to Slack.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create config.json and the database")
    p_init.add_argument("--force", action="store_true")

    sub.add_parser("refresh", help="pull the chart and new releases, derive signals")

    p_serve = sub.add_parser("serve", help="start the web dashboard")
    p_serve.add_argument("--port", default=None)
    p_serve.add_argument("--host", default=None)

    d = sub.add_parser("digest", help="build and send a Slack digest")
    d.add_argument("period", choices=["daily", "weekly"])
    d.add_argument("--dry-run", action="store_true",
                   help="print the Slack payload instead of sending it")

    r = sub.add_parser("run", help="refresh then send a digest (for scheduled jobs)")
    r.add_argument("period", choices=["daily", "weekly"])
    r.add_argument("--dry-run", action="store_true")

    sub.add_parser("slack-test", help="post a connection test to Slack")
    c = sub.add_parser("chart", help="print the stored chart")
    c.add_argument("--limit", type=int, default=100)

    e = sub.add_parser("export", help="render the static site and Slack payloads")
    e.add_argument("--outdir", default="site")
    e.add_argument("--prune", action="store_true",
                   help="trim old snapshots before exporting")

    s = sub.add_parser("schedule", help="manage macOS launchd jobs")
    s.add_argument("action", choices=["install", "uninstall", "status"])
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    cfg = config.load()
    handlers = {
        "init": cmd_init, "refresh": cmd_refresh, "digest": cmd_digest,
        "run": cmd_run, "slack-test": cmd_slack_test, "serve": cmd_serve,
        "chart": cmd_chart, "schedule": cmd_schedule, "export": cmd_export,
    }
    return handlers[args.cmd](args, cfg)
