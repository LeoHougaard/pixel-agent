import { tool } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"
import { homedir } from "os"
import { join } from "path"

const BASE = process.env.PIXEL_PHONE_URL ?? "http://127.0.0.1:18080"

function token(): string {
  if (process.env.PIXEL_PHONE_TOKEN) return process.env.PIXEL_PHONE_TOKEN
  const file = process.env.PIXEL_PHONE_TOKEN_FILE ?? join(homedir(), ".config", "pixel-phone", "bridge-token")
  if (!existsSync(file)) throw new Error(`Missing bridge token at ${file}. In Termux run: pixel-phone-bridge`)
  return readFileSync(file, "utf-8").trim()
}

async function call(path: string, body?: unknown, timeoutMs = 70000): Promise<string> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Authorization": `Bearer ${token()}`,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    })
    const text = await res.text()
    if (!res.ok) throw new Error(`bridge ${path} HTTP ${res.status}: ${text.slice(0, 2000)}`)
    return text
  } finally {
    clearTimeout(t)
  }
}

export default tool({
  description: "Run a shell command on the Pixel: privileged=false for Termux files/packages/network, privileged=true for Android shell (am, pm, cmd, input, settings, screencap). Prefer structured Android CLIs over tapping.",
  args: {
    command: tool.schema.string().describe("Exact shell command to execute"),
    privileged: tool.schema.boolean().describe("true for Android ADB-shell identity, false for Termux").default(false),
    timeout: tool.schema.number().describe("Timeout 1-300s").default(60),
  },
  async execute(args) {
    return await call("/run", { command: args.command, privileged: args.privileged, timeout: args.timeout }, (Math.min(300, Math.max(1, args.timeout)) + 10) * 1000)
  },
})
