import test from 'node:test';
import assert from 'node:assert/strict';
import { activity } from '../pixel-t3-watch.mjs';

const clients = { leases: [] };
const thread = { session: { status: 'ready', activeTurnId: null }, latestTurn: { state: 'completed' } };

test('a disconnected client does not make a running task idle', () => {
  for (const active of [
    { session: { status: 'starting' } },
    { session: { status: 'running' } },
    { session: { status: 'ready', activeTurnId: 'turn-1' } },
    { latestTurn: { state: 'running' } },
    { backgroundLiveness: 'working' },
    { titleRegeneration: { requestId: 'title-1' } },
  ]) assert.equal(activity({ threads: [{ ...thread, ...active }] }, clients).busy, true);
});

test('reading chat keeps it available; hidden and expired clients do not', () => {
  const visible = { visible: true, expiresAt: new Date(Date.now() + 60000).toISOString() };
  const shell = { threads: [thread] };
  assert.deepEqual(activity(shell, { leases: [visible] }), { busy: false, foreground: true });
  for (const lease of [
    { ...visible, visible: false },
    { ...visible, appState: 'background' },
    { ...visible, expiresAt: '2000-01-01T00:00:00Z' },
  ]) assert.deepEqual(activity(shell, { leases: [lease] }), { busy: false, foreground: false });
});

test('unknown server state cannot authorize shutdown', () => {
  assert.throws(() => activity({}, clients));
  assert.throws(() => activity({ threads: [{ session: { status: 'new-upstream-state' } }] }, clients));
  assert.throws(() => activity({ threads: [] }, { leases: [{ visible: true }] }));
});
