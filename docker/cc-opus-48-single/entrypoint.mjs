import { readFileSync, appendFileSync, writeFileSync, mkdirSync, cpSync, existsSync, createWriteStream } from "fs";
import { spawn } from "child_process";

mkdirSync("/output", { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}

let claudeProc = null;

process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  claudeProc?.kill("SIGTERM");
  process.exit(0);
});

log("Starting entrypoint");

// Install custom skills and agents into ~/.claude/ for the running user.
const HOME = process.env.HOME || "/home/node";
for (const dir of ["skills", "agents"]) {
  const src = `/app/${dir}`;
  const dst = `${HOME}/.claude/${dir}`;
  if (existsSync(src)) {
    mkdirSync(dst, { recursive: true });
    cpSync(src, dst, { recursive: true, force: true });
    log(`Installed ${dir} into ${dst}`);
  }
}

const prompt = readFileSync("/workspace/prompt.md", "utf-8");
log("Starting claude code session");

claudeProc = spawn("claude", ["-p", prompt, "--dangerously-skip-permissions", "--model", "claude-opus-4-8", "--effort", "high", "--verbose", "--output-format", "stream-json", "--agent", "coordinator"], {
  cwd: "/workspace",
  env: process.env,
});

const agentStdoutStream = createWriteStream("/output/agent_stdout.log", { flags: "a" });
const agentStderrStream = createWriteStream("/output/agent_stderr.log", { flags: "a" });

claudeProc.stdout.on("data", (chunk) => {
  process.stdout.write(chunk);
  agentStdoutStream.write(chunk);
});

claudeProc.stderr.on("data", (chunk) => {
  process.stderr.write(chunk);
  agentStderrStream.write(chunk);
});

claudeProc.on("exit", (code) => {
  log(`Session complete with exit code ${code}`);
  writeFileSync("/output/exit_code", String(code ?? 0));
  process.exit(code ?? 0);
});
