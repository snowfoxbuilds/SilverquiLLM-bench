import { createAgentSession, AuthStorage, ModelRegistry, SessionManager } from "@earendil-works/pi-coding-agent";
import { readFileSync, appendFileSync, writeFileSync, mkdirSync, createWriteStream } from "fs";

mkdirSync("/output", { recursive: true });

function log(msg) {
  const ts = new Date().toISOString().substring(11, 19);
  appendFileSync("/output/system.log", `[${ts}] ${msg}\n`);
}

process.on("SIGTERM", () => {
  log("Received SIGTERM, shutting down");
  appendFileSync("/output/progress.jsonl",
    JSON.stringify({ ts: new Date().toISOString(), status: "timed_out" }) + "\n"
  );
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
  // All 4 default tools: read, bash, edit, write
});

const agentStdoutStream = createWriteStream("/output/agent_stdout.log", { flags: "a" });

// Stream progress to mounted volume
log("Session created, subscribing to events");
session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    const delta = event.assistantMessageEvent.delta;
    process.stdout.write(delta);
    agentStdoutStream.write(delta);
  }
  if (event.type === "tool_execution_end") {
    appendFileSync("/output/progress.jsonl",
      JSON.stringify({ ts: new Date().toISOString(), tool: event.toolName }) + "\n"
    );
  }
});

// Read prompt and go
log("Starting session with prompt");
const prompt = readFileSync("/workspace/prompt.md", "utf-8");
const result = await session.prompt(prompt);
log("Session complete");

writeFileSync("/output/exit_code", "0");
process.exit(0);