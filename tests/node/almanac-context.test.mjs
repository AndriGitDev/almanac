import test from 'node:test';
import assert from 'node:assert/strict';
import { ContextGeneration } from '../../extensions/almanac-context.js';

test('compaction rejects an in-flight old generation and restores recovery on next request', () => {
  const host = new ContextGeneration('instance');
  const args = { cwd:'/repo', sessionId:'s', prompt:'current intent', maxChars:4000 };
  const old = host.request(args);
  assert.ok(old.args.includes('fresh'));
  host.compact();
  assert.equal(host.returned(old), false);
  const recovery = host.request(args);
  assert.ok(recovery.args.includes('post_compaction'));
  assert.ok(recovery.args.includes('1'));
  assert.equal(host.returned(recovery), true);
  assert.ok(host.request(args).args.includes('resume'));
});

test('independent host instances and failed requests do not share delivery state', () => {
  const a = new ContextGeneration('a');
  const b = new ContextGeneration('b');
  a.compact();
  const args = { cwd:'/repo', sessionId:'s', prompt:'intent', maxChars:32 };
  assert.ok(a.request(args).args.includes('post_compaction'));
  assert.ok(a.request(args).args.includes('post_compaction')); // failed/no packet: recovery retained
  assert.ok(b.request(args).args.includes('fresh'));
});
