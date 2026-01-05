import express from "express";
import bodyParser from "body-parser";
import fs from "fs/promises";
import path from "path";
import { pathToFileURL } from "url";

const app = express();
app.use(bodyParser.json({ limit: "2mb" }));

const PLUGIN_DIR = process.env.PLUGIN_DIR || "/plugin";
const ENTRY_FILE = process.env.ENTRY || "entry.js";

async function loadEntry() {
  const abs = path.join(PLUGIN_DIR, ENTRY_FILE);
  await fs.stat(abs); // throws if not found
  // bust cache on every call (simple dev mode)
  return import(pathToFileURL(abs).href + `?t=${Date.now()}`);
}

app.get("/healthz", (_req, res) => res.json({ ok: true, runner: "ai-plugin-runner" }));

app.post("/run", async (req, res) => {
  try {
    const mod = await loadEntry();
    if (!mod.run || typeof mod.run !== "function") {
      throw new Error("Plugin export 'run(input, ctx)' is missing");
    }
    const timeoutMs = Number(process.env.TIMEOUT_MS || 8000);
    const ctx = { env: { NODE_ENV: process.env.NODE_ENV || "production" }, metadata: req.body?.metadata || {} };
    const result = await Promise.race([
      mod.run(req.body?.input || {}, ctx),
      new Promise((_, rej) => setTimeout(() => rej(new Error("Plugin timed out")), timeoutMs))
    ]);
    res.json({ ok: true, result });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e?.message || e) });
  }
});

const PORT = Number(process.env.PORT || 9000);
app.listen(PORT, () => console.log(`[runner] listening on ${PORT}`));
