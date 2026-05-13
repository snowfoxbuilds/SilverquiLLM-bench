import { createAgentSession, AuthStorage, ModelRegistry, SessionManager } from "@earendil-works/pi-coding-agent";
import { readFileSync, appendFileSync, writeFileSync, cpSync } from "fs";

// ---------------------------------------------------------------------------
// Multi-channel output helpers
// ---------------------------------------------------------------------------

/**
 * Log a system/orchestration message to /output/system.log (not agent streams).
 */
function log(msg) {
  const ts = new Date().toISOString().slice(11, 19);  // HH:MM:SS
  const line = `[${ts}] ${msg}\n`;
  appendFileSync("/output/system.log", line);
  // Also echo to stdout so `docker logs` still shows orchestration
  process.stdout.write(line);
}

/**
 * Append timestamped text to /output/agent_stdout.log.
 */
function agentStdout(text) {
  const ts = new Date().toISOString().slice(11, 19);  // HH:MM:SS
  const stamped = `[${ts}] ${text}`;
  appendFileSync("/output/agent_stdout.log", stamped);
  process.stdout.write(stamped);
}

/**
 * Append timestamped text to /output/agent_stderr.log.
 */
function agentStderr(text) {
  const ts = new Date().toISOString().slice(11, 19);  // HH:MM:SS
  const stamped = `[${ts}] ${text}`;
  appendFileSync("/output/agent_stderr.log", stamped);
  process.stderr.write(stamped);
}

// ---------------------------------------------------------------------------
// Entrypoint
// ---------------------------------------------------------------------------

// Intercept process-level stderr so agent runtime errors are captured
const _origStderrWrite = process.stderr.write.bind(process.stderr);
process.stderr.write = (chunk, encoding, callback) => {
  const ts = new Date().toISOString().slice(11, 19);
  const text = typeof chunk === "string" ? chunk : chunk.toString();
  try { appendFileSync("/output/agent_stderr.log", `[${ts}] ${text}`); } catch {}
  return _origStderrWrite(chunk, encoding, callback);
};

let exitCode = 1;
try {
  log("Starting entrypoint");

  // Copy engine to writable location
  log("Copying engine to engine_work/");
  cpSync("/workspace/engine", "/workspace/engine_work", { recursive: true });
  log("Engine copied");

  // Set up Pi
  log("Setting up Pi agent");
  const authStorage = AuthStorage.create();
  const modelRegistry = ModelRegistry.create(authStorage);

  // Find local model
  log("Looking for model in registry");
  const model = modelRegistry.find("llamacpp", "default");
  if (!model) {
    agentStderr("FATAL: model not found in registry\n");
    agentStderr("Available: " + JSON.stringify(await modelRegistry.getAvailable()) + "\n");
    exitCode = 1;
  } else {
    log("Model found, creating session");
    const { session } = await createAgentSession({
      cwd: "/workspace",
      model,
      sessionManager: SessionManager.inMemory(),
      authStorage,
      modelRegistry,
      // All 4 default tools: read, bash, edit, write
    });

    // Stream progress to mounted volume
    log("Session created, subscribing to events");
    session.subscribe((event) => {
      if (event.type === "message_update" && event.assistantMessageEvent.type === "text_delta") {
        // Agent text output → agent_stdout channel
        agentStdout(event.assistantMessageEvent.delta);
      }
      if (event.type === "tool_execution_end") {
        appendFileSync("/output/progress.jsonl",
          JSON.stringify({ ts: new Date().toISOString(), tool: event.toolName }) + "\n"
        );
      }
    });

    // Read prompt and go
    log("Building prompt");
    const prompt = readFileSync("/workspace/prompt.md", "utf-8");
    log("Launching agent");
    const result = await session.prompt(prompt);
    log("Agent finished");

    // Write result summary to agent_stdout
    agentStdout("\n--- Session Result ---\n");
    agentStdout(JSON.stringify(result, null, 2) + "\n");

    exitCode = 0;
  }
} catch (err) {
  log(`FATAL ERROR: ${err.message}`);
  agentStderr(`${err.stack || err.message}\n`);
  exitCode = 1;
} finally {
  log("Writing exit code");
  writeFileSync("/output/exit_code", String(exitCode));
  log("Entrypoint complete");
  process.exit(exitCode);
}