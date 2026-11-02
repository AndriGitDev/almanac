import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

// Execute the real adapter handlers with the host event API mocked. Node 22.18+'s
// native TS stripping avoids introducing a production transpiler dependency.
test('real Pi handlers discard pre-compaction packets and request generation recovery', { skip: Number(process.versions.node.split('.')[0]) < 22 || (Number(process.versions.node.split('.')[0]) === 22 && Number(process.versions.node.split('.')[1]) < 18) }, async () => {
  const { registerHooks } = await import('node:module');
  const typebox = 'data:text/javascript,' + encodeURIComponent('export const Type = new Proxy({}, {get:()=>()=>({})});');
  const tui = 'data:text/javascript,' + encodeURIComponent('export class Text { constructor(){} render(){return [];} } export const Key = new Proxy({}, {get:()=>()=>""}); export const matchesKey=()=>false; export const truncateToWidth=(s)=>s; export const visibleWidth=(s)=>s.length;');
  const hooks = registerHooks({ resolve(specifier, context, nextResolve) {
    if (specifier === 'typebox') return { url:typebox, shortCircuit:true };
    if (specifier === '@mariozechner/pi-tui') return { url:tui, shortCircuit:true };
    if (specifier.startsWith('.') && specifier.endsWith('.js') && context.parentURL?.startsWith('file:')) {
      const target = new URL(specifier.replace(/\.js$/, '.ts'), context.parentURL);
      if (existsSync(fileURLToPath(target))) return nextResolve(target.href, context);
    }
    return nextResolve(specifier, context);
  }});
  const oldComposer = process.env.ALMANAC_PI_CONTEXT_COMPOSER;
  const oldCapture = process.env.ALMANAC_PI_AUTO_CAPTURE;
  process.env.ALMANAC_PI_CONTEXT_COMPOSER = 'true';
  process.env.ALMANAC_PI_AUTO_CAPTURE = 'false';
  try {
    const { default: activate } = await import(new URL('../../extensions/almanac.ts', import.meta.url).href);
    const handlers = new Map();
    let releaseOld;
    const requests = [];
    const api = new Proxy({
      on(name, handler) { handlers.set(name, handler); },
      async exec(_command, args) {
        if (args.includes('session-context')) {
          requests.push(args);
          if (requests.length === 1) return await new Promise(resolve => { releaseOld = resolve; });
          return {code:0, stdout:JSON.stringify({should_inject:true, content:'Complete recovery caveat.', schema:'almanac-context/v1'})};
        }
        return {code:0, stdout:'{}'};
      },
    }, { get(target, key) { return target[key] ?? (()=>{}); } });
    activate(api);
    const cwd = await mkdtemp(join(tmpdir(), 'almanac-native-events-'));
    const ctx = { cwd, hasUI:false, signal:new AbortController().signal,
      ui:new Proxy({}, {get:()=>()=>{}}), sessionManager:{getSessionFile:()=>'/fixture/session'}, isIdle:()=>true };
    await handlers.get('session_start')({}, ctx);
    const old = handlers.get('before_agent_start')({prompt:'current intent'}, ctx);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(typeof releaseOld, 'function');
    await handlers.get('session_compact')({}, ctx);
    releaseOld({code:0, stdout:JSON.stringify({should_inject:true, content:'obsolete packet'})});
    assert.equal(await old, undefined);
    const recovered = await handlers.get('before_agent_start')({prompt:'current intent'}, ctx);
    assert.equal(recovered.message.content, 'Complete recovery caveat.');
    assert.ok(requests[1].includes('post_compaction'));
    assert.equal(requests[1][requests[1].indexOf('--context-epoch') + 1], '1');
    assert.equal(requests[0][requests[0].indexOf('--host-instance-id') + 1], requests[1][requests[1].indexOf('--host-instance-id') + 1]);
  } finally {
    hooks.deregister();
    if (oldComposer === undefined) delete process.env.ALMANAC_PI_CONTEXT_COMPOSER; else process.env.ALMANAC_PI_CONTEXT_COMPOSER = oldComposer;
    if (oldCapture === undefined) delete process.env.ALMANAC_PI_AUTO_CAPTURE; else process.env.ALMANAC_PI_AUTO_CAPTURE = oldCapture;
  }
});
