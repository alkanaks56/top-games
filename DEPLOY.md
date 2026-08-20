# Deploying (free, no machine of your own)

Three free services, each doing what it is good at:

| Piece | Runs on | Job |
|---|---|---|
| Data pull + Slack digests | GitHub Actions | Scheduled Python, same code as local |
| Team dashboard | GitHub Pages | Static site, public URL |
| `/top100` slash command | Cloudflare Workers | Always-on, verifies Slack, serves prebuilt payloads |

The SQLite database is committed back to the repo on each run. That is deliberate: it is the
only state that survives between runs, and without it every run would look like a first run and
detect no chart movement at all.

---

## 1. Push to GitHub

```bash
cd /Users/alkan/Desktop/workspace/tools/top_games
git init && git add -A && git commit -m "Initial commit"
```

Create a repo on GitHub, then:

```bash
git remote add origin https://github.com/<you>/top-games.git && git branch -M main && git push -u origin main
```

`config.json` is gitignored, so your webhook and signing secret are **not** pushed.

## 2. Add the Slack webhook as a secret

Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

- Name: `SLACK_WEBHOOK_URL`
- Value: your `https://hooks.slack.com/services/...` URL

The workflow reads it via `TOPGAMES_SLACK_WEBHOOK`. Secrets are encrypted and are not visible in
logs, including on public repos.

## 3. Turn on Pages

Repo → **Settings** → **Pages** → **Source: GitHub Actions**. Do not pick a branch.

## 4. Run it once by hand

Repo → **Actions** → **Update charts and publish** → **Run workflow** → set *send_digest* to
`none` for the first run.

The first run only stores a baseline; there is nothing to compare against yet. Run it a second
time to start producing movement signals.

When it finishes, the run summary links your Pages URL — something like
`https://<you>.github.io/top-games`. That is the team dashboard. Share it as-is; it is public
and has no API routes, so there is nothing to abuse.

## 5. Deploy the slash-command Worker

```bash
npm install -g wrangler
```

```bash
wrangler login
```

Edit `worker/wrangler.toml` and set `PAGES_BASE` to the Pages URL from step 4. Then:

```bash
cd worker && wrangler secret put SLACK_SIGNING_SECRET
```

Paste the signing secret from your Slack app (**Basic Information → App Credentials**). Finally:

```bash
cd worker && wrangler deploy
```

Wrangler prints a URL like `https://topgames-slash.<you>.workers.dev`.

## 6. Point Slack at the Worker

Slack app → **Slash Commands** → edit `/top100`:

| Field | Value |
|---|---|
| Command | `/top100` |
| Request URL | `https://topgames-slash.<you>.workers.dev` |
| Short Description | `Print the App Store Top 100 Apps` |

Save, then **reinstall the app** when Slack shows the yellow banner. Slash commands do not
activate until you reinstall.

This URL never changes again — no more tunnels.

---

## Changing the schedule

Edit the `cron` line in `.github/workflows/update.yml` (UTC). The workflow sends the weekly
digest on Mondays and the daily digest otherwise.

## Things that will bite you eventually

- **GitHub's scheduled runs are best-effort.** Jobs can start minutes to hours late under load.
  If exact timing matters, this is the wrong scheduler.
- **Scheduled workflows switch off after 60 days without repo activity.** The bot's own data
  commits count as activity, so this only matters if the workflow is failing silently. Check
  Actions occasionally.
- **`/top100 refresh` cannot pull on demand.** The data is whatever the last scheduled run
  published; the command says so rather than pretending.
- **The committed database grows.** `export --prune` (already in the workflow) keeps the last
  180 snapshots and 120 days of events. Rows in `apps` are never deleted, because `first_seen`
  is what stops a game being announced as new twice.
