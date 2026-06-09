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

log("Starting entrypoint (execution-only, prepared plan)");

// Install the execute-todo skill into ~/.claude/skills for the running user.
// Skills auto-discover from ~/.claude/skills/<name>/SKILL.md; the bare agent
// loads it when the prompt tells it to run the skill.
const HOME = process.env.HOME || "/home/node";
const skillSrc = "/app/skills";
const skillDst = `${HOME}/.claude/skills`;
if (existsSync(skillSrc)) {
  mkdirSync(skillDst, { recursive: true });
  cpSync(skillSrc, skillDst, { recursive: true, force: true });
  log(`Installed skills into ${skillDst}`);
}

// Stage the baked-in execution plan into the workspace so the skill can read it.
// These are agent-prompt-layer artifacts (not part of the Workspace Contract);
// they are copied in at launch, after the runner has staged the workspace.
cpSync("/app/TODO.md", "/workspace/TODO.md", { force: true });
cpSync("/app/CONTEXT.md", "/workspace/CONTEXT.md", { force: true });
log("Copied TODO.md and CONTEXT.md into /workspace");

// The task and plan live entirely in the baked-in files; the prompt just starts
// the skill. The card list and rules are in TODO.md / CONTEXT.md.
const prompt = [
  "Run the `execute-todo` skill now to implement the SOS cards.",
  "Your task and prepared execution plan are in /workspace/TODO.md and /workspace/CONTEXT.md.",
].join("\n");

// Fable 5. The build-time `@anthropic-ai/claude-code` must recognize this model id.
const MODEL = "claude-fable-5";

log(`Starting claude code session (${MODEL}, effort xhigh)`);

claudeProc = spawn("claude", ["-p", prompt, "--dangerously-skip-permissions", "--model", MODEL, "--effort", "xhigh", "--verbose", "--output-format", "stream-json"], {
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
