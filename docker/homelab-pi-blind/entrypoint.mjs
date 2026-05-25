import { createAgentSession, AuthStorage, ModelRegistry, SessionManager } from "@earendil-works/pi-coding-agent";
import { readFileSync, appendFileSync, writeFileSync, mkdirSync, createWriteStream } from "fs";

mkdirSync("/output", { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}

process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  process.exit(0);
});

log("Starting entrypoint");

// Set up Pi
const authStorage = AuthStorage.create();
const modelRegistry = ModelRegistry.create(authStorage);

// Find local model
log("Looking for model in registry");
const model = modelRegistry.find("llamacpp", "default");
if (!model) {
  log("FATAL: model not found in registry");
  console.error("FATAL: model not found in registry");
  console.error("Available:", JSON.stringify(await modelRegistry.getAvailable()));
  process.exit(1);
}

log("Model found, creating session");
const { session } = await createAgentSession({
  cwd: "/workspace",
  model,
  sessionManager: SessionManager.inMemory(),
  authStorage,
  modelRegistry,
  thinkingLevel: "high",
  // All 4 default tools: read, bash, edit, write
});

const agentStdoutStream = createWriteStream("/output/agent_stdout.log", { flags: "a" });

const agentStderrStream = createWriteStream("/output/agent_stderr.log", { flags: "a" });

session.subscribe((event) => {
  if (event.type === "message_update") {
    const sub = event.assistantMessageEvent;
    if (sub.type === "text_delta") {
      process.stdout.write(sub.delta);
      agentStdoutStream.write(sub.delta);
    } else if (sub.type === "thinking_delta") {
      process.stderr.write(sub.delta);
      agentStderrStream.write(sub.delta);
    }
  }

  if (event.type === "tool_execution_end") {
    log(`Tool executed: ${event.toolName}`);
  }
});

// Read prompt and go
log("Starting session with prompt");
const prompt = readFileSync("/workspace/prompt.md", "utf-8");
const result = await session.prompt(prompt);
log("Session complete");

writeFileSync("/output/exit_code", "0");
process.exit(0);