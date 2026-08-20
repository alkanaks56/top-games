"""Command line entry point."""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from . import config, signals, slack, staticgen, store, web
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


def cmd_refresh(args, cfg):
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
    conn = store.connect()
    payload, ids = slack.build_digest(conn, cfg, args.period)
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
    conn = store.connect()
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
