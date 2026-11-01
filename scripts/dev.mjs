#!/usr/bin/env node
// One command for local development: `npm run dev` (from the repo root).
// Starts Postgres/Redis (Docker, best effort), applies migrations, then runs the API and the website together with prefixed output.
// Ctrl+C stops everything. `npm run install:all` does the one-time Python and Node installs.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const py = join(root, ".venv", process.platform === "win32" ? "Scripts" : "bin", process.platform === "win32" ? "python.exe" : "python");
const run = (cmd, args, cwd = root) => spawnSync(cmd, args, { cwd, stdio: "inherit", shell: process.platform === "win32" });

if (process.argv.includes("--setup")) {
  if (!existsSync(py)) run("python3", ["-m", "venv", ".venv"]);
  run(py, ["-m", "pip", "install", "-e", "data_pipeline[parquet]", "-e", "quant_engine[research]", "-e", "backend[dev]"]);
  run("npm", ["install"], join(root, "frontend"));
  process.exit(0);
}

if (!existsSync(py)) {
  console.error("Python environment not found. Run `npm run install:all` first (or see README).");
  process.exit(1);
}
if (!existsSync(join(root, "frontend", "node_modules"))) {
  console.error("Frontend dependencies not found. Run `npm run install:all` first.");
  process.exit(1);
}

const docker = run("docker", ["compose", "up", "-d", "--wait", "postgres", "redis"]);
if (docker.status !== 0) console.warn("\n[dev] Could not start Postgres with Docker. If you run your own Postgres, set QSMF_DATABASE_URL; otherwise start Docker and retry.\n");
else if (run(py, ["-m", "alembic", "upgrade", "head"], join(root, "backend")).status !== 0) console.warn("[dev] Migrations failed; the API may not work.");

const colour = { api: "\x1b[36m", web: "\x1b[35m" };
const children = [];
function start(name, cmd, args, cwd) {
  // own process group (POSIX) so stopping kills the whole tree: npm -> next, uvicorn reloader -> worker
  const p = spawn(cmd, args, { cwd, env: { ...process.env, FORCE_COLOR: "1" }, shell: process.platform === "win32", detached: process.platform !== "win32" });
  const out = (s) => String(s).split(/\r?\n/).filter(Boolean).forEach((l) => console.log(`${colour[name]}[${name}]\x1b[0m ${l}`));
  p.stdout.on("data", out);
  p.stderr.on("data", out);
  p.on("exit", (code) => { console.log(`[${name}] exited (${code})`); stop(code ?? 0); });
  children.push(p);
}
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  const kill = (sig) => children.forEach((c) => {
    try { process.platform === "win32" ? c.kill(sig) : process.kill(-c.pid, sig); } catch { /* already gone */ }
  });
  kill("SIGTERM");
  setTimeout(() => { kill("SIGKILL"); process.exit(code); }, 2000);
}
process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

start("api", py, ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], join(root, "backend"));
start("web", "npm", ["run", "dev"], join(root, "frontend"));
console.log("\n  API:  http://localhost:8000/docs\n  Site: http://localhost:3000\n  Ctrl+C stops both.\n");
