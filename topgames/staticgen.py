"""Render the tracker as a static site plus pre-built Slack payloads.

GitHub Pages serves plain files, so the dashboard ships with its data inlined
rather than fetching from an API. The same run also writes the Slack slash
command responses, which lets the Cloudflare Worker stay a thin, near-zero-CPU
proxy: it verifies the request signature and returns a file built here.
"""
import json
import os
from datetime import datetime, timezone

from . import command, slack, store, viewdata
from .static_template import BODY, SCRIPT, STYLE

COUNTRY_NAMES = {"us": "United States", "gb": "United Kingdom", "de": "Germany",
                 "fr": "France", "jp": "Japan", "tr": "Türkiye", "ca": "Canada",
                 "au": "Australia", "kr": "South Korea", "cn": "China"}

PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>__TITLE__</title>
<style>__STYLE__</style></head><body>
__BODY__
<script>__SCRIPT__</script>
</body></html>
"""


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def build(conn, cfg, outdir="site"):
    """Write the static site and the Slack payloads the Worker will serve."""
    view = viewdata.build(conn, cfg)
    if view is None:
        raise RuntimeError("no chart data stored yet -- run `topgames refresh` first")

    genre = cfg["genre"].replace("_", " ").title()
    country = cfg["country"].upper()
    country_name = COUNTRY_NAMES.get(cfg["country"].lower(), country)
    stats = store.stats(conn)

    data = dict(view)
    data.update({
        "genre": genre,
        "country": country,
        "country_name": country_name,
        "new_days": cfg["signals"]["new_release_days"],
        "db": stats,
        "digest": {
            "daily_time": cfg["slack"]["daily"].get("time", "09:00"),
            "daily": cfg["slack"]["daily"].get("include", []),
            "weekly_day": cfg["slack"]["weekly"].get("day", "monday").title(),
            "weekly_time": cfg["slack"]["weekly"].get("time", "09:00"),
            "weekly": cfg["slack"]["weekly"].get("include", []),
        },
        "worker_url": cfg["web"].get("worker_url", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })

    repo = cfg["web"].get("repo_url", "")
    actions = f"{repo}/actions/workflows/update.yml" if repo else "#"
    title = f"{genre}, {country_name} — Top {cfg['chart_size']}"

    html = (PAGE
            .replace("__STYLE__", STYLE)
            .replace("__BODY__", BODY
                     .replace("__SCOPE__", f"{cfg['country']} · ios · {cfg['genre']}")
                     .replace("__SYNC__", view["captured_at"][11:16])
                     .replace("__ACTIONS__", actions))
            .replace("__SCRIPT__", SCRIPT.replace("__DATA__",
                     json.dumps(data, default=str)))
            .replace("__TITLE__", title))

    _write(os.path.join(outdir, "index.html"), html)
    # Tells GitHub Pages to publish files and folders beginning with an underscore.
    _write(os.path.join(outdir, ".nojekyll"), "")
    _write(os.path.join(outdir, "data", "chart.json"),
           json.dumps(data, indent=1, default=str))

    # Pre-render every slash-command response so the Worker does no real work.
    payloads = {
        "top100-25": command._chart_reply(conn, cfg, 25, False),
        "top100-50": command._chart_reply(conn, cfg, 50, False),
        "top100-100": command._chart_reply(conn, cfg, cfg["chart_size"], False),
        "new": command._new_reply(conn, cfg, False),
        "signals": command._signals_reply(conn, cfg, False),
        "help": command._reply([command._section(command.HELP)], "help"),
    }
    for name, payload in payloads.items():
        _write(os.path.join(outdir, "slack", f"{name}.json"),
               json.dumps(payload, default=str))

    # Payloads the Worker forwards verbatim when someone presses Share.
    for kind in ("movers", "new", "chart"):
        share = slack.build_share(conn, cfg, kind)
        if share:
            _write(os.path.join(outdir, "slack", f"share-{kind}.json"),
                   json.dumps(share, default=str))

    return {"outdir": outdir, "chart_rows": len(view["items"]),
            "new": sum(1 for i in view["items"] if i["is_new_release"]),
            "events": len(view["movers"]),
            "publishers": len(view["publishers"]),
            "span_days": view["span_days"],
            "slack_payloads": sorted(payloads)}
