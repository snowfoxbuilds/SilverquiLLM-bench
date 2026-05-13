import { createAgentSession, AuthStorage, ModelRegistry, SessionManager } from "@earendil-works/pi-coding-agent";
import { readFileSync, appendFileSync, writeFileSync, cpSync } from "fs";

console.log("Starting entrypoint...");

// Copy engine to writable location
cpSync("/workspace/engine", "/workspace/engine_work", { recursive: true });

// Set up Pi
console.log("Engine copied, setting up Pi...");
const authStorage = AuthStorage.create();
const modelRegistry = ModelRegistry.create(authStorage);

// Find local model
console.log("Looking for model in registry...");
const model = modelRegistry.find("llamacpp", "default");
if (!model) {
  console.error("FATAL: model not found in registry");
  console.error("Available:", JSON.stringify(await modelRegistry.getAvailable()));
  process.exit(1);
}

console.log("Model found, creating session...");
const { session } = await createAgentSession({
  cwd: "/workspace",
  model,
  sessionManager: SessionManager.inMemory(),
  authStorage,
  modelRegistry,
  // All 4 default tools: read, bash, edit, write
});

// Stream progress to mounted volume
console.log("Session created, subscribing to events...");
session.subscribe((event) => {
  if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
    process.stdout.write(event.assistantMessageEvent.delta);
  }
  if (event.type === "tool_execution_end") {
    appendFileSync("/output/progress.jsonl",
      JSON.stringify({ ts: new Date().toISOString(), tool: event.toolName }) + "\n"
    );
  }
});

// Read prompt and go
console.log("Starting session with prompt...");
const prompt = readFileSync("/workspace/prompt.md", "utf-8");
const result =await session.prompt(prompt);
console.log("Session result:", JSON.stringify(result, null, 2));

console.log("Session complete, writing exit code...");
writeFileSync("/output/exit_code", "0");
process.exit(0);