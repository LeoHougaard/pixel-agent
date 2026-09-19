import { tool } from "@opencode-ai/plugin"
import { readFileSync, existsSync, mkdirSync, writeFileSync } from "fs"
import { homedir, tmpdir } from "os"
import { join } from "path"

const BASE = process.env.PIXEL_PHONE_URL ?? "http://127.0.0.1:18080"

function token(): string {
  if (process.env.PIXEL_PHONE_TOKEN) return process.env.PIXEL_PHONE_TOKEN
  const file = process.env.PIXEL_PHONE_TOKEN_FILE ?? join(homedir(), ".config", "pixel-phone", "bridge-token")
  if (!existsSync(file)) throw new Error(`Missing bridge token at ${file}. In Termux run: pixel-phone-bridge`)
  return readFileSync(file, "utf-8").trim()
}

export default tool({
  description: "Capture the Android screen. Saves PNG and returns its path + dimensions; read the file as an image before acting.",
  args: {},
  async execute() {
    const res = await fetch(`${BASE}/screenshot`, {
      headers: { "Authorization": `Bearer ${token()}` },
    })
    if (!res.ok) throw new Error(`screenshot HTTP ${res.status}: ${(await res.text()).slice(0, 1000)}`)
    const bytes = Buffer.from(await res.arrayBuffer())
    if (bytes.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a") throw new Error("bridge did not return PNG")
    const w = bytes.readUInt32BE(16)
    const h = bytes.readUInt32BE(20)
    const dir = join(tmpdir(), "pixel-phone")
    mkdirSync(dir, { recursive: true })
    const path = join(dir, `screen-${Date.now()}.png`)
    writeFileSync(path, bytes)
    return JSON.stringify({ path, width: w, height: h, hint: `Read ${path} as an image, then use pixel_ui_tap/swipe/key/type or pixel_run.` })
  },
})
