"""Configuration loading and defaults."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(ROOT, "config.json")
DB_PATH = os.path.join(ROOT, "data", "topgames.db")

# Apple App Store genre ids. 6014 is Games; the 70xx range are its subgenres.
GENRES = {
    "games": 6014, "action": 7001, "adventure": 7002, "casual": 7003,
    "board": 7004, "card": 7005, "casino": 7006, "dice": 7007,
    "educational": 7008, "family": 7009, "music": 7011, "puzzle": 7012,
    "racing": 7013, "role_playing": 7014, "simulation": 7015, "sports": 7016,
    "strategy": 7017, "trivia": 7018, "word": 7019,
}

DEFAULTS = {
    "country": "us",
    "genre": "puzzle",
    "chart": "topfreeapplications",
    "chart_size": 100,
    "slack": {
        "webhook_url": "",
        # Only needed for the /top100 slash command, not for digests.
        "signing_secret": "",
        "username": "Top Games Bot",
        "icon_emoji": ":jigsaw:",
        # Which signals get posted, and in which digest.
        # Text prepended to every digest, e.g. "<!here>" or "<!subteam^ID>".
        "mention": "",
        "daily": {
            "enabled": True,
            "time": "09:00",
            "include": ["debut", "new_entry", "new_release", "climb", "exit"],
            # Skip posting entirely on a day with nothing to report, instead of
            # sending "no new games" into the channel every morning.
            "skip_if_empty": False,
            # Append the current top N. 0 turns the section off.
            "show_top_n": 0,
            "title": "",          # blank uses "Daily <Genre> Games Report"
        },
        "weekly": {
            "enabled": True,
            "day": "monday",
            "time": "09:00",
            "include": ["debut", "new_entry", "new_release", "climb", "fall", "exit"],
            "skip_if_empty": False,
            "show_top_n": 10,
            "title": "",
            "show_full_chart": True,
        },
        # Post the moment a new game enters the chart, without waiting for a digest.
        "realtime_new_entry": False,
    },
    "signals": {
        # A rank move of at least this many places is worth reporting.
        "move_threshold": 10,
        # An app counts as a "new release" if published within this many days.
        "new_release_days": 30,
        # Cap list lengths in Slack so messages stay readable.
        "max_items_per_section": 10,
    },
    "search_terms": [
        "puzzle", "jigsaw", "sudoku", "match 3", "block puzzle", "word puzzle",
        "brain", "escape room", "merge", "tile", "crossword", "logic",
        "hidden object", "solitaire", "nonogram",
    ],
    "web": {
        "host": "127.0.0.1", "port": 8765,
        # When the server is reached through a tunnel or proxy, only the signed
        # /slack/command endpoint is served. Set true to publish the dashboard
        # and its unauthenticated /api routes as well -- rarely what you want.
        "expose_dashboard": False,
        # Linked from the dashboard's "Send digest" control.
        "repo_url": "https://github.com/alkanaks56/top-games",
    },
}


def _merge(base, override):
    """Deep-merge override into a copy of base."""
    out = dict(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], val)
        else:
            out[key] = val
    return out


# Environment overrides, so CI can supply secrets without a config file in the repo.
ENV_MAP = {
    "TOPGAMES_SLACK_WEBHOOK": ("slack", "webhook_url"),
    "TOPGAMES_SLACK_SIGNING_SECRET": ("slack", "signing_secret"),
    "TOPGAMES_GENRE": ("genre",),
    "TOPGAMES_COUNTRY": ("country",),
    "TOPGAMES_CHART": ("chart",),
}


def _apply_env(cfg):
    for var, path in ENV_MAP.items():
        value = os.environ.get(var)
        if not value:
            continue
        target = cfg
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = value
    return cfg


def load(path=CONFIG_PATH):
    user = {}
    if os.path.exists(path):
        with open(path) as fh:
            user = json.load(fh)
    cfg = _apply_env(_merge(DEFAULTS, user))
    cfg["genre_id"] = GENRES.get(cfg["genre"], GENRES["puzzle"])
    return cfg


def save_example(path=None):
    path = path or os.path.join(ROOT, "config.example.json")
    with open(path, "w") as fh:
        json.dump(DEFAULTS, fh, indent=2)
    return path
