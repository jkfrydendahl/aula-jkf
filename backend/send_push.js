#!/usr/bin/env node
/**
 * send_push.js — send a single Web Push notification via web-push (Node.js).
 * Called from Python PushService as a subprocess.
 *
 * Reads a JSON payload from stdin:
 * {
 *   "endpoint": "...",
 *   "keys": { "p256dh": "...", "auth": "..." },
 *   "title": "...",
 *   "body": "...",
 *   "vapid_public_key": "...",
 *   "vapid_private_key": "...",
 *   "vapid_email": "..."
 * }
 *
 * Exits 0 on success, 1 on failure (error written to stderr).
 */

const webpush = require("web-push");

let raw = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => (raw += chunk));
process.stdin.on("end", () => {
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (e) {
    process.stderr.write("Failed to parse stdin JSON: " + e.message + "\n");
    process.exit(1);
  }

  const { endpoint, keys, title, body, vapid_public_key, vapid_private_key, vapid_email } = payload;

  webpush.setVapidDetails(
    vapid_email.startsWith("mailto:") ? vapid_email : `mailto:${vapid_email}`,
    vapid_public_key,
    vapid_private_key
  );

  const subscription = { endpoint, keys };
  const notification = JSON.stringify({ title, body });

  webpush
    .sendNotification(subscription, notification)
    .then(() => {
      process.stdout.write("ok\n");
      process.exit(0);
    })
    .catch((err) => {
      process.stderr.write(
        `Push failed: ${err.statusCode} ${err.body || err.message}\n`
      );
      process.exit(1);
    });
});
