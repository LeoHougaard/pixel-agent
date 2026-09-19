import { tool } from '@opencode-ai/plugin'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const exec = promisify(execFile)
export default tool({
  description: 'Use the full Debian/XFCE desktop on this Pixel, including OrcaSlicer. Start only when needed; poll status until ready. Screenshot returns an image path to read. Mouse coordinates are desktop pixels. launch runs a Linux command with DISPLAY=:1. Use the normal bash tool for files, coding and packages. show opens the desktop on the phone. stop closes only an agent-started desktop.',
  args: {
    action: tool.schema.enum(['start','status','stop','show','screenshot','launch','click','move','drag','scroll','key','type']),
    command: tool.schema.string().optional().describe('Linux launch command, for example orca-slicer-pixel'),
    x: tool.schema.number().optional(), y: tool.schema.number().optional(),
    end_x: tool.schema.number().optional(), end_y: tool.schema.number().optional(),
    button: tool.schema.number().optional().describe('1 left, 2 middle, 3 right'),
    clicks: tool.schema.number().optional().describe('1 or 2'),
    direction: tool.schema.enum(['up','down']).optional(), amount: tool.schema.number().optional(),
    key: tool.schema.string().optional().describe('X11 key combination, for example Return, ctrl+s, alt+F4'),
    text: tool.schema.string().optional(),
  },
  async execute(args) {
    try {
      const result=await exec('python3',['/usr/local/lib/pixel-agent/pixel-desktop-control.py',JSON.stringify(args)],{timeout:60000,maxBuffer:1024*1024})
      return result.stdout.trim()
    } catch(error:any) {
      throw new Error(error.stdout?.trim() || 'Desktop tool did not respond. Check desktop status.')
    }
  },
})
