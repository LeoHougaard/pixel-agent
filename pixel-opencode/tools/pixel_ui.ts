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

async function call(path: string, body?: unknown): Promise<string> {
  const res = await fetch(`${BASE}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Authorization": `Bearer ${token()}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  if (!res.ok) throw new Error(`bridge ${path} HTTP ${res.status}: ${text.slice(0, 2000)}`)
  return text
}

export const tap = tool({
  description: "Tap the Android screen. x/y are 0-1000 normalized by default.",
  args: {
    x: tool.schema.number().describe("Horizontal 0-1000 (or pixels with normalized=false)"),
    y: tool.schema.number().describe("Vertical 0-1000 (or pixels with normalized=false)"),
    normalized: tool.schema.boolean().default(true),
  },
  async execute(args) {
    return await call("/tap", args)
  },
})

export const inspect = tool({
  description: "Inspect the current Android screen: labeled controls, text, enabled state and tap centers. Use before phone actions; refresh after navigation. Use pixel_screenshot for unlabeled/canvas UI.",
  args: {},
  async execute() { return await call('/ui') },
})

export const long_press = tool({
  description: "Long-press an Android control. Coordinates are normalized 0-1000.",
  args: { x: tool.schema.number(), y: tool.schema.number(), duration_ms: tool.schema.number().default(800) },
  async execute(a) { return await call('/swipe', { sx:a.x, sy:a.y, ex:a.x, ey:a.y, duration_ms:a.duration_ms, normalized:true }) },
})

export const swipe = tool({
  description: "Swipe/drag on Android. Use for scrolls and drags.",
  args: {
    sx: tool.schema.number(), sy: tool.schema.number(),
    ex: tool.schema.number(), ey: tool.schema.number(),
    duration_ms: tool.schema.number().default(500),
    normalized: tool.schema.boolean().default(true),
  },
  async execute(args) {
    return await call("/swipe", args)
  },
})

export const key = tool({
  description: "Press an Android key: BACK, HOME, RECENTS, ENTER, TAB, ESC, DEL, arrows, VOLUME_UP/DOWN, or KEYCODE_*.",
  args: { key: tool.schema.string() },
  async execute(args) {
    return await call("/key", args)
  },
})

export const type = tool({
  description: "Type text via clipboard paste (unicode-safe). Set press_enter to submit.",
  args: {
    text: tool.schema.string(),
    press_enter: tool.schema.boolean().default(false),
  },
  async execute(args) {
    return await call("/type", args)
  },
})

export const open_app = tool({
  description: "Open an Android app by friendly name (gmail, photos, settings, chrome, ...) or package. Call list_apps first if unsure.",
  args: { app: tool.schema.string() },
  async execute(args) {
    return await call("/open_app", args)
  },
})

export const list_apps = tool({
  description: "List launchable Android activities (package/component).",
  args: {},
  async execute() {
    return await call("/apps")
  },
})
