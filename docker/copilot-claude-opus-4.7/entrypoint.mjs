import { readFileSync, appendFileSync, writeFileSync, mkdirSync, cpSync, existsSync, createWriteStream } from "fs";
import { spawn } from "child_process";

mkdirSync("/output", { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}

let copilotProc = null;

process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  copilotProc?.kill("SIGTERM");
  process.exit(0);
});

log("Starting entrypoint");

// Install custom skills and agents into the mounted ~/.copilot/ config
for (const dir of ["skills", "agents"]) {
  const src = `/app/${dir}`;
  const dst = `/root/.copilot/${dir}`;
  if (existsSync(src)) {
    mkdirSync(dst, { recursive: true });
    cpSync(src, dst, { recursive: true, force: true });
    log(`Installed ${dir} into copilot config`);
  }
}

const prompt = readFileSync("/workspace/prompt.md", "utf-8");
log("Starting copilot session");

copilotProc = spawn("copilot", ["-p", prompt, "--yolo", "--model=claude-opus-4.7", "--agent=coordinator", "--effort=medium"], {
  cwd: "/workspace",
  env: { ...process.env, HOME: "/root" },
});

const agentStdoutStream = createWriteStream("/output/agent_stdout.log", { flags: "a" });
const agentStderrStream = createWriteStream("/output/agent_stderr.log", { flags: "a" });

copilotProc.stdout.on("data", (chunk) => {
  process.stdout.write(chunk);
  agentStdoutStream.write(chunk);
});

copilotProc.stderr.on("data", (chunk) => {
  process.stderr.write(chunk);
  agentStderrStream.write(chunk);
});

copilotProc.on("exit", (code) => {
  log(`Session complete with exit code ${code}`);
  writeFileSync("/output/exit_code", String(code ?? 0));
  process.exit(code ?? 0);
});
