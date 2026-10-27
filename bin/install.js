#!/usr/bin/env node
// Installs the user-guide-builder skill into every AI tool it finds on this machine.
// No dependencies. Usage: npx github:RandomKid24/adys-docyfy-skill [options]
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const readline = require("readline");
const { spawnSync } = require("child_process");

const NAME = "user-guide-builder";
const SRC = path.join(__dirname, "..");
const COPY = ["SKILL.md", "README.md", "requirements.txt", "assets", "references", "scripts"];
const home = process.env.HOME || os.homedir();
const xdg = process.env.XDG_CONFIG_HOME || path.join(home, ".config");

// detect = a folder that exists when the tool is installed. dir = where its skills live.
// "sure" tools load SKILL.md folders as documented. The rest are best effort.
const TOOLS = [
  { id: "claude", label: "Claude Code", detect: path.join(home, ".claude"), dir: path.join(home, ".claude", "skills"), sure: true },
  { id: "opencode", label: "OpenCode", detect: path.join(xdg, "opencode"), dir: path.join(xdg, "opencode", "skill"), sure: true },
  { id: "codex", label: "Codex CLI", detect: path.join(home, ".codex"), dir: path.join(home, ".codex", "skills"), sure: false },
  { id: "gemini", label: "Gemini CLI", detect: path.join(home, ".gemini"), dir: path.join(home, ".gemini", "skills"), sure: false },
  { id: "cursor", label: "Cursor", detect: path.join(home, ".cursor"), dir: path.join(home, ".cursor", "skills"), sure: false },
];

const args = process.argv.slice(2);
const has = (f) => args.includes(f);
const val = (f) => { const i = args.indexOf(f); return i >= 0 ? args[i + 1] : null; };

if (has("-h") || has("--help")) {
  console.log(`user-guide-builder installer

  npx github:RandomKid24/adys-docyfy-skill            find AI tools and install
  --yes, -y         do not ask, install to everything found
  --project         install into ./.claude/skills in the current folder only
  --target <dir>    install into this skills folder
  --tool <id>       only this tool: ${TOOLS.map((t) => t.id).join(", ")}
  --list            show what was found, install nothing
  --uninstall       remove the skill from the places it is installed
  --no-deps         skip the pip install step
`);
  process.exit(0);
}

function targets() {
  if (val("--target")) return [{ label: "custom folder", dir: path.resolve(val("--target")), sure: true }];
  if (has("--project")) return [{ label: "this project", dir: path.resolve(".claude", "skills"), sure: true }];
  let list = TOOLS.filter((t) => fs.existsSync(t.detect));
  if (val("--tool")) list = TOOLS.filter((t) => t.id === val("--tool"));
  return list;
}

function copyDir(from, to) {
  fs.mkdirSync(to, { recursive: true });
  for (const e of fs.readdirSync(from, { withFileTypes: true })) {
    if (e.name === "__pycache__" || e.name.endsWith(".pyc")) continue;
    const a = path.join(from, e.name), b = path.join(to, e.name);
    e.isDirectory() ? copyDir(a, b) : fs.copyFileSync(a, b);
  }
}

function install(dir) {
  const dest = path.join(dir, NAME);
  fs.rmSync(dest, { recursive: true, force: true });
  fs.mkdirSync(dest, { recursive: true });
  for (const f of COPY) {
    const a = path.join(SRC, f), b = path.join(dest, f);
    if (!fs.existsSync(a)) continue;
    fs.statSync(a).isDirectory() ? copyDir(a, b) : fs.copyFileSync(a, b);
  }
  return dest;
}

function ask(q) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((res) => rl.question(q, (a) => { rl.close(); res(a.trim().toLowerCase()); }));
}

function pythonDeps() {
  for (const py of ["python3", "python"]) {
    const ok = spawnSync(py, ["--version"], { stdio: "ignore" });
    if (ok.status !== 0) continue;
    const req = path.join(SRC, "requirements.txt");
    const base = ["-m", "pip", "install", "-q", "-r", req];
    let r = spawnSync(py, base, { stdio: "inherit" });
    if (r.status !== 0) r = spawnSync(py, [...base, "--user", "--break-system-packages"], { stdio: "inherit" });
    return r.status === 0;
  }
  console.log("Python 3 not found. Install it, then run: pip install -r requirements.txt");
  return false;
}

(async () => {
  const found = targets();
  if (!found.length) {
    console.log("No supported AI tool found. Use --target <skills folder> or --project.");
    process.exit(1);
  }
  console.log("Found:");
  for (const t of found) console.log(`  ${t.label}${t.sure ? "" : " (best effort)"}  ${t.dir}`);
  if (has("--list")) return;

  if (has("--uninstall")) {
    for (const t of found) {
      const d = path.join(t.dir, NAME);
      if (fs.existsSync(d)) { fs.rmSync(d, { recursive: true, force: true }); console.log(`Removed ${d}`); }
    }
    return;
  }

  if (!has("--yes") && !has("-y") && process.stdin.isTTY) {
    const a = await ask("\nInstall into all of these? [Y/n] ");
    if (a === "n" || a === "no") { console.log("Nothing installed."); return; }
  }
  for (const t of found) {
    try { console.log(`Installed: ${install(t.dir)}`); }
    catch (e) { console.log(`Could not install for ${t.label}: ${e.message}`); }
  }
  if (!has("--no-deps")) {
    console.log("\nInstalling Python packages...");
    if (!pythonDeps()) console.log("Packages not installed. Run: pip install -r requirements.txt (path above)");
  }
  console.log(`\nDone. Restart your AI tool, then ask it: "make a user guide for my app at http://localhost:3000".
You also need the Claude in Chrome extension for screenshots.`);
})();
