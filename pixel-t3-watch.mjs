// Runs in Debian. Reports actual T3 client/task state without reading chat text.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as sleep } from 'node:timers/promises';
import { pathToFileURL } from 'node:url';

const exec = promisify(execFile);
const base = 'http://127.0.0.1:3773';

export function activity(shell, policy) {
  if (!Array.isArray(shell.threads) || !Array.isArray(policy.leases)) {
    throw new Error('Unsupported T3 activity response');
  }
  const states = new Set(['idle', 'starting', 'running', 'ready', 'interrupted', 'stopped', 'error']);
  let busy = false;
  for (const thread of shell.threads) {
    if (thread.session && !states.has(thread.session.status)) {
      throw new Error('Unknown T3 session state');
    }
    busy ||= ['starting', 'running'].includes(thread.session?.status)
      || Boolean(thread.session?.activeTurnId)
      || thread.latestTurn?.state === 'running'
      || Boolean(thread.backgroundLiveness)
      || Boolean(thread.titleRegeneration);
  }
  // Do not count this monitor as a client. It never reports an activity lease.
  const foreground = policy.leases.some(lease => {
    if (typeof lease.visible !== 'boolean' || !Number.isFinite(Date.parse(lease.expiresAt))) {
      throw new Error('Unsupported T3 client lease');
    }
    return lease.visible && lease.appState !== 'background'
      && Date.parse(lease.expiresAt) > Date.now();
  });
  return { busy, foreground };
}

async function json(path, token, method = 'GET') {
  const response = await fetch(base + path, {
    method, headers: { Authorization: `Bearer ${token}` },
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`T3 status HTTP ${response.status}`);
  return response.json();
}

export async function policy(token) {
  return rpc(token, 'server.getBackgroundPolicy', {});
}

export async function rpc(token, tag, payload) {
  const { ticket } = await json('/api/auth/websocket-ticket', token, 'POST');
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:3773/ws?wsTicket=${encodeURIComponent(ticket)}`);
    let settled = false;
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      ws.close();
      error ? reject(error) : resolve(value);
    };
    const timer = setTimeout(() => finish(new Error('T3 activity check timed out')), 10000);
    ws.onopen = () => ws.send(JSON.stringify({
      _tag: 'Request', id: '1', tag, payload, headers: [],
    }));
    ws.onerror = () => finish(new Error('T3 activity connection failed'));
    ws.onclose = () => finish(new Error('T3 activity connection closed'));
    ws.onmessage = event => {
      try {
        const messages = JSON.parse(event.data);
        for (const message of Array.isArray(messages) ? messages : [messages]) {
          if (message._tag === 'Ping') ws.send(JSON.stringify({ _tag: 'Pong' }));
          if (message._tag === 'Exit' && message.requestId === '1') {
            if (message.exit?._tag !== 'Success') throw new Error('T3 activity request failed');
            finish(null, message.exit.value);
          }
        }
      } catch { finish(new Error('Invalid T3 activity response')); }
    };
  });
}

async function main(entry) {
  let session;
  let stopping = false;
  const revoke = async () => {
    if (!session) return;
    const id = session.sessionId;
    session = undefined;
    await exec(process.execPath, [entry, 'auth', 'session', 'revoke', id], { timeout: 20000 }).catch(() => {});
  };
  for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => {
    if (stopping) return;
    stopping = true;
    revoke().finally(() => process.exit(0));
  });
  while (!stopping) {
    try {
      if (!session || Date.parse(session.expiresAt) - Date.now() < 60000) {
        await revoke();
        const { stdout } = await exec(process.execPath, [entry, 'auth', 'session', 'issue',
          '--ttl', '2h', '--label', 'Pixel idle monitor', '--json'], { timeout: 60000 });
        session = JSON.parse(stdout);
      }
      const [shell, clients] = await Promise.all([
        json('/api/orchestration/shell', session.token), policy(session.token),
      ]);
      console.log(JSON.stringify({ ok: true, ...activity(shell, clients), time: Date.now() / 1000 }));
    } catch {
      // Never print tokens, websocket tickets, API bodies, or command errors.
      console.log(JSON.stringify({ ok: false, time: Date.now() / 1000 }));
    }
    await sleep(15000);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main(process.argv[2]);
}
