// Optional integration check against an isolated T3 server on port 3773.
// Set PIXEL_T3_TEST_ENTRY and T3CODE_HOME to the test installation/state.
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as sleep } from 'node:timers/promises';
import { activity, policy } from '../pixel-t3-watch.mjs';

test('real T3 reports visible chat and expires its lease after disconnection', {
  skip: !process.env.PIXEL_T3_TEST_ENTRY, timeout: 90000,
}, async () => {
  const entry = process.env.PIXEL_T3_TEST_ENTRY;
  const exec = promisify(execFile);
  const { stdout } = await exec(process.execPath, [entry, 'auth', 'session', 'issue',
    '--ttl', '5m', '--label', 'Pixel lifecycle test', '--json']);
  const session = JSON.parse(stdout);
  const clientId = `pixel-test-${Date.now()}`;
  const ownPolicy = async () => ({ leases: (await policy(session.token)).leases.filter(lease => lease.clientId === clientId) });
  let ws;
  try {
    const response = await fetch('http://127.0.0.1:3773/api/auth/websocket-ticket', {
      method: 'POST', headers: { Authorization: `Bearer ${session.token}` },
    });
    assert.equal(response.status, 200);
    const { ticket } = await response.json();
    ws = new WebSocket(`ws://127.0.0.1:3773/ws?wsTicket=${encodeURIComponent(ticket)}`);
    await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
    const accepted = new Promise((resolve, reject) => {
      ws.onmessage = event => {
        const message = JSON.parse(event.data);
        if (message._tag === 'Exit' && message.requestId === 'visible') {
          message.exit._tag === 'Success' ? resolve() : reject(new Error('Activity report rejected'));
        }
      };
    });
    ws.send(JSON.stringify({ _tag: 'Request', id: 'visible', tag: 'server.reportClientActivity', headers: [],
      payload: { clientId, clientKind: 'web', visible: true, focused: true,
        recentlyInteracted: true, scopes: [], ttlMs: 1000, observedAt: new Date().toISOString() } }));
    await accepted;
    assert.equal(activity({ threads: [] }, await ownPolicy()).foreground, true);
    ws.close();
    await sleep(1500);
    assert.equal(activity({ threads: [] }, await ownPolicy()).foreground, false);
  } finally {
    ws?.close();
    await exec(process.execPath, [entry, 'auth', 'session', 'revoke', session.sessionId]);
  }
});
