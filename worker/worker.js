/**
 * Slack slash-command endpoint for /top100.
 *
 * All the real work happens in the scheduled GitHub Action, which publishes
 * ready-made Slack payloads to GitHub Pages. This Worker only verifies that a
 * request genuinely came from Slack and hands back the matching file, which
 * keeps it far inside the free plan's 10ms CPU budget.
 */

const REPLAY_WINDOW = 60 * 5; // seconds

const enc = new TextEncoder();

function hex(buf) {
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Length-independent comparison, so timing cannot leak the expected signature. */
function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function verify(secret, timestamp, signature, body) {
  if (!secret) return "no signing secret configured";
  if (!timestamp || !signature) return "missing signature headers";
  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp));
  if (!Number.isFinite(age) || age > REPLAY_WINDOW) return "stale timestamp";
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`v0:${timestamp}:${body}`));
  return safeEqual(`v0=${hex(mac)}`, signature) ? null : "signature mismatch";
}

const HELP_TEXT =
  "*`/top100` — App Store chart lookup*\n" +
  "`/top100` — top 25 · `/top100 50` · `/top100 100`\n" +
  "`/top100 new` — recent releases\n" +
  "`/top100 signals` — chart movement\n" +
  "`/top100 share` — post the top 25 to the channel\n";

function message(text, inChannel = false) {
  return {
    response_type: inChannel ? "in_channel" : "ephemeral",
    text: text.replace(/[*`<>|]/g, ""),
    blocks: [{ type: "section", text: { type: "mrkdwn", text } }],
  };
}

/** Map the user's argument onto one of the published payload files. */
function route(text) {
  const t = (text || "").trim().toLowerCase();
  if (t === "" || t === "25") return { file: "top100-25" };
  if (t === "50") return { file: "top100-50" };
  if (t === "100") return { file: "top100-100" };
  if (/^\d+$/.test(t)) {
    const n = Number(t);
    return { file: n <= 25 ? "top100-25" : n <= 50 ? "top100-50" : "top100-100" };
  }
  if (t.startsWith("new")) return { file: "new" };
  if (t.startsWith("signal")) return { file: "signals" };
  if (t.startsWith("share")) return { file: "top100-25", inChannel: true };
  if (t === "help" || t === "?") return { inline: message(HELP_TEXT) };
  if (t === "refresh") {
    return { inline: message(
      ":information_source: Data refreshes automatically on a schedule — there is " +
      "nothing to trigger by hand. The timestamp on the dashboard shows how current " +
      "it is.") };
  }
  return { inline: message(`:question: Unknown option \`${t}\`.\n\n${HELP_TEXT}`) };
}

const SHARE_KINDS = new Set(["movers", "new", "chart"]);
const SHARE_COOLDOWN = 60; // seconds between shares of the same kind

function cors(env, extra = {}) {
  // Only the published dashboard may call this from a browser.
  let origin = "*";
  try { origin = new URL(env.PAGES_BASE).origin; } catch {}
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    ...extra,
  };
}

/**
 * Forward a prebuilt payload to Slack.
 *
 * The body carries only a kind, never text: the message itself is a file the
 * scheduled job published, so this endpoint cannot be used to post arbitrary
 * content into the channel. A short cooldown bounds how often a public page can
 * trigger it.
 */
async function handleShare(request, env) {
  if (!env.SLACK_WEBHOOK_URL) {
    return Response.json({ error: "Worker has no SLACK_WEBHOOK_URL secret set" },
      { status: 500, headers: cors(env) });
  }
  let kind = "";
  try { kind = (await request.json()).kind; } catch {}
  if (!SHARE_KINDS.has(kind)) {
    return Response.json({ error: "unknown share kind" },
      { status: 400, headers: cors(env) });
  }

  const cache = caches.default;
  const marker = new Request(`https://share.local/${kind}`);
  if (await cache.match(marker)) {
    return Response.json(
      { error: `Already shared ${kind} in the last ${SHARE_COOLDOWN}s` },
      { status: 429, headers: cors(env) });
  }

  const src = `${env.PAGES_BASE.replace(/\/$/, "")}/slack/share-${kind}.json`;
  let payload;
  try {
    const res = await fetch(src, { cf: { cacheTtl: 60 } });
    if (!res.ok) throw new Error(`upstream ${res.status}`);
    payload = await res.json();
  } catch (err) {
    return Response.json({ error: `Could not load the message (${err.message})` },
      { status: 502, headers: cors(env) });
  }

  const post = await fetch(env.SLACK_WEBHOOK_URL, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!post.ok) {
    const detail = await post.text().catch(() => "");
    return Response.json({ error: `Slack rejected it (${post.status} ${detail})` },
      { status: 502, headers: cors(env) });
  }

  await cache.put(marker, new Response("1", {
    headers: { "Cache-Control": `max-age=${SHARE_COOLDOWN}` } }));
  return Response.json({ ok: true, message: `Posted ${kind} to Slack` },
    { headers: cors(env) });
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors(env) });
    }
    if (path === "/share") {
      if (request.method !== "POST") {
        return new Response("share endpoint", { status: 405, headers: cors(env) });
      }
      return handleShare(request, env);
    }
    if (request.method !== "POST") {
      return new Response("top100 slash command endpoint", { status: 405 });
    }
    const body = await request.text();
    const problem = await verify(
      env.SLACK_SIGNING_SECRET,
      request.headers.get("X-Slack-Request-Timestamp"),
      request.headers.get("X-Slack-Signature"),
      body);
    if (problem) {
      // Deliberately terse: an unverified request may not be from Slack at all.
      return new Response("unauthorized", { status: 401 });
    }

    const form = new URLSearchParams(body);
    const target = route(form.get("text"));
    if (target.inline) {
      return Response.json(target.inline);
    }

    const url = `${env.PAGES_BASE.replace(/\/$/, "")}/slack/${target.file}.json`;
    let payload;
    try {
      const upstream = await fetch(url, { cf: { cacheTtl: 300, cacheEverything: true } });
      if (!upstream.ok) {
        return Response.json(message(
          `:warning: Could not load chart data (upstream ${upstream.status}). ` +
          `The scheduled job may not have published yet.`));
      }
      payload = await upstream.json();
    } catch (err) {
      // A network failure or malformed JSON must still produce a Slack-shaped
      // reply; an exception here would surface to the user as a raw error.
      return Response.json(message(
        ":warning: Chart data is temporarily unreachable. Please try again shortly."));
    }
    if (target.inChannel) payload.response_type = "in_channel";
    return Response.json(payload);
  },
};
