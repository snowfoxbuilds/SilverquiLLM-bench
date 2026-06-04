import { readFileSync, appendFileSync, writeFileSync, mkdirSync, cpSync, existsSync, createWriteStream } from "fs";
import { spawn } from "child_process";

mkdirSync("/output", { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}

let currentProc = null;

process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  currentProc?.kill("SIGTERM");
  process.exit(0);
});

log("Starting entrypoint (two-phase plan->TDD flow)");

// Install skills (tdd + grep-rulebook) into ~/.claude/skills for the running
// user. Skills auto-discover from ~/.claude/skills/<name>/SKILL.md; both phases
// run as bare single agents (no --agent), loading the skills on demand.
const HOME = process.env.HOME || "/home/node";
const src = "/app/skills";
const dst = `${HOME}/.claude/skills`;
if (existsSync(src)) {
  mkdirSync(dst, { recursive: true });
  cpSync(src, dst, { recursive: true, force: true });
  log(`Installed skills into ${dst}`);
}

const task = readFileSync("/workspace/prompt.md", "utf-8");
const plannerPreamble = readFileSync("/app/phase1_planner.md", "utf-8");
const implementerPreamble = readFileSync("/app/phase2_implementer.md", "utf-8");

// Aggregate logs span both phases so the result gatherer's token parser sees
// all usage; per-phase logs make each session inspectable on its own.
const aggStdout = createWriteStream("/output/agent_stdout.log", { flags: "a" });
const aggStderr = createWriteStream("/output/agent_stderr.log", { flags: "a" });

function runClaude(promptText, label) {
  return new Promise((resolve) => {
    log(`Phase '${label}': starting claude session`);
    const proc = spawn(
      "claude",
      ["-p", promptText, "--dangerously-skip-permissions", "--model", "claude-opus-4-8", "--effort", "xhigh", "--verbose", "--output-format", "stream-json"],
      { cwd: "/workspace", env: process.env },
    );
    currentProc = proc;

    const phaseStdout = createWriteStream(`/output/${label}_stdout.log`, { flags: "a" });
    const phaseStderr = createWriteStream(`/output/${label}_stderr.log`, { flags: "a" });

    proc.stdout.on("data", (chunk) => {
      process.stdout.write(chunk);
      aggStdout.write(chunk);
      phaseStdout.write(chunk);
    });
    proc.stderr.on("data", (chunk) => {
      process.stderr.write(chunk);
      aggStderr.write(chunk);
      phaseStderr.write(chunk);
    });
    proc.on("exit", (code) => {
      log(`Phase '${label}': complete with exit code ${code}`);
      currentProc = null;
      resolve(code ?? 0);
    });
  });
}

const SEP = "\n\n---\n\n";

// Phase 1 — planning. Writes /workspace/PLAN.md; runs no implementation.
await runClaude(plannerPreamble + SEP + task, "planner");
if (existsSync("/workspace/PLAN.md")) {
  log("PLAN.md written by planner phase");
} else {
  log("WARNING: PLAN.md not found after planner phase; implementer will proceed from the task directly");
}

// Phase 2 — implementation. Reads PLAN.md and implements every card with TDD.
const implCode = await runClaude(implementerPreamble + SEP + task, "implementer");

log(`Session complete with implementer exit code ${implCode}`);
writeFileSync("/output/exit_code", String(implCode ?? 0));
process.exit(implCode ?? 0);
