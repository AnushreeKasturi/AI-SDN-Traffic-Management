import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

test('the embedded experiment datasets match their committed sources', () => {
  new vm.Script(script);
  for (const [pattern, path] of [
    [/const DATA = (\{.*?\});/s, '../results/results.json'],
    [/\/\* HYBRID-DATA \*\/const HYBRID = (\{.*?\});\/\* \/HYBRID-DATA \*\//s, '../results/hybrid_v3/dashboard.json'],
  ]) {
    assert.deepEqual(JSON.parse(html.match(pattern)[1]), JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8')));
  }
});

test('repeated chart redraws keep their height at pixel ratios 1, 2, and 3', () => {
  const sizing = script.match(/function setupCanvas\(canvas\) \{[\s\S]*?\n\}/)[0];
  for (const dpr of [1, 2, 3]) {
    const context = vm.createContext({ window: { devicePixelRatio: dpr } });
    vm.runInContext(sizing, context);
    const canvas = {
      parentElement: { clientWidth: 600 }, height: 230, style: {}, dataset: {},
      getAttribute(name) { return String(this[name]); },
      getContext() { return { setTransform() {} }; },
    };
    for (let i = 0; i < 12; i++) {
      context.setupCanvas(canvas);
      assert.equal(canvas.style.height, '230px');
      assert.equal(canvas.height, 230 * dpr);
      assert.equal(canvas.width, 600 * dpr);
    }
  }
});

test('light, typical, and heavy traffic match the pre-redesign routing baselines', () => {
  const engine = script.match(/const LINKS = \[[\s\S]*?(?=\/\/ ---- wire up the demo panel ----)/)[0];
  for (const [parameters, expected] of [
    [{ flowsPerInterval: 22, nIntervals: 24, intensity: 1, seed: 42 }, '613286d437d6fc0e317524d59f9f77e2307b2fbc4db5364cf4e7e66f59b236a0'],
    [{ flowsPerInterval: 5, nIntervals: 8, intensity: 0.3, seed: 7 }, '1479e5a26ab7651db1b3f9c8e13106c1879ae89cbd26996ba9df7c4120e37cbd'],
    [{ flowsPerInterval: 80, nIntervals: 60, intensity: 3, seed: 123 }, '4e1d749259533b28551b928cf2023b7c4573d8a968640c394767512938b74498'],
  ]) {
    const result = vm.runInNewContext(`${engine}\nrunLiveSimulation(${JSON.stringify(parameters)})`);
    const normalized = JSON.stringify(result, (_, value) => typeof value === 'number' ? Number(value.toFixed(6)) : value);
    assert.equal(createHash('sha256').update(normalized).digest('hex'), expected);
  }
});
