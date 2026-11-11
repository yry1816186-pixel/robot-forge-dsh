/** Runtime test for the DSH host half: registration, tools, and real Python gates. */
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { apply } from '../index.js';

const tools = new Map();
const sections = [];
let commands = 0;
const fakeCtx = {
  tools: {
    register(definition) {
      tools.set(definition.name, definition);
      return () => tools.delete(definition.name);
    },
  },
  systemPrompt: {
    section(section) {
      sections.push(section);
      return () => {};
    },
  },
  get(name) {
    if (name !== 'commands') return undefined;
    return {
      register() {
        commands += 1;
        return () => {};
      },
    };
  },
};

const dispose = apply(fakeCtx);
const expected = [
  'rf_intake', 'rf_blueprints', 'rf_new', 'rf_status', 'rf_check', 'rf_design',
  'rf_verify', 'rf_audit', 'rf_trace', 'rf_review', 'rf_package', 'rf_evidence',
];
assert.deepEqual([...tools.keys()].sort(), expected.sort(), 'all twelve tools are registered');
assert.equal(sections.length, 1, 'one prompt section is registered');
assert.equal(commands, 1, 'the human /forge command is registered');

for (const definition of tools.values()) {
  assert.ok(definition.description.length > 20, definition.name + ' has a description');
  assert.equal(definition.parameters.type, 'object');
  assert.equal(typeof definition.execute, 'function');
  assert.equal(typeof definition.output.render, 'function');
}

const temp = mkdtempSync(join(tmpdir(), 'rf-dsh-'));
const exec = { signal: new AbortController().signal, agent: { session: { cwd: temp } } };
try {
  const intake = await tools.get('rf_intake').execute(
    { text: '做一台能跟着我走、避开障碍的小车，预算 300 元', budget: 300 },
    exec,
  );
  assert.equal(intake.ok, true, intake.text);
  assert.equal(intake.data.archetype, 'wheel-rover', intake.text);
  assert.equal(intake.data.budget_cny, 300, intake.text);
  assert.ok(Array.isArray(intake.data.questions) && intake.data.questions.length <= 3, intake.text);

  const refused = await tools.get('rf_intake').execute({ text: '做一个偷拍邻居卧室的机器人' }, exec);
  assert.equal(refused.ok, false, 'intake refuses tracking/privacy-abuse intents');
  assert.match(refused.text, /安全替代/);

  const blueprints = await tools.get('rf_blueprints').execute({}, exec);
  assert.equal(blueprints.ok, true);
  assert.match(blueprints.text, /desktop-companion/);

  const noBlueprint = await tools.get('rf_new').execute(
    { name: '无蓝本测试', dir: temp, slug: 'test-noblueprint' },
    exec,
  );
  assert.equal(noBlueprint.ok, false, 'rf_new rejects a missing blueprint');
  assert.match(noBlueprint.text, /blueprint 必填/);

  const badSlug = await tools.get('rf_new').execute(
    { name: '危险目录测试', blueprint: 'wheel-rover', dir: temp, slug: '../evil' },
    exec,
  );
  assert.equal(badSlug.ok, false, 'rf_new rejects a path-traversal slug');
  assert.match(badSlug.text, /slug/);

  const created = await tools.get('rf_new').execute(
    { name: '测试小车', blueprint: 'wheel-rover', dir: temp, slug: 'test-rover' },
    exec,
  );
  assert.equal(created.ok, true, created.text);
  const project = created.data.project;
  assert.ok(project.endsWith('test-rover'));

  const status = await tools.get('rf_status').execute({ project }, exec);
  assert.equal(status.ok, true, status.text);
  assert.match(status.text, /测试小车/);

  const checked = await tools.get('rf_check').execute({ project }, exec);
  assert.equal(checked.ok, true, checked.text);
  assert.equal(checked.data.check.stats.errors, 0, checked.text);

  const design = await tools.get('rf_design').execute({ project }, exec);
  assert.equal(design.ok, true, design.text);
  assert.ok(design.data.torque.required_kgcm > 0, design.text);
  assert.ok(design.data.power.runtime_h > 0, design.text);
  assert.ok(readFileSync(join(project, 'forge', 'design.md'), 'utf8').includes('设计核算'));

  const traced = await tools.get('rf_trace').execute({ project }, exec);
  assert.equal(traced.data.must, 6, traced.text);
  assert.ok(traced.data.coverage >= 0 && traced.data.coverage <= 100, traced.text);
  assert.ok(readFileSync(join(project, 'forge', 'trace.md'), 'utf8').includes('must 覆盖'));

  const reviewed = await tools.get('rf_review').execute({ project }, exec);
  assert.equal(reviewed.ok, false, 'an unverified project is not ready for a blind review');
  const packet = JSON.parse(readFileSync(join(project, 'forge', 'review-packet.json'), 'utf8'));
  assert.match(packet.packet_sha256, /^[0-9a-f]{64}$/);
  assert.ok(packet.trace, 'review packet embeds the trace matrix');

  const blockedPackage = await tools.get('rf_package').execute({ project }, exec);
  assert.equal(blockedPackage.ok, false, 'unverified projects cannot be packaged');
  assert.match(blockedPackage.text, /拒绝/);

  const verified = await tools.get('rf_verify').execute({ project }, exec);
  assert.equal(verified.ok, true, verified.text);
  assert.match(verified.text, /PASS/);
  assert.equal(verified.data.failures, 0, verified.text);
  assert.ok(verified.data.results.length >= 5, 'the full verify suite runs every command');
  assert.ok(verified.data.evidence_ids.length >= 4, 'passing required commands are recorded as evidence');

  const audited = await tools.get('rf_audit').execute({ project }, exec);
  assert.equal(audited.ok, false, 'a new project with unverified must requirements cannot pass audit');
  assert.match(audited.text, /不可发布|Beta/);
  assert.ok(typeof audited.data.score === 'number');

  for (const req of ['REQ-001', 'REQ-002', 'REQ-003', 'REQ-004', 'REQ-005', 'REQ-006']) {
    const simulated = await tools.get('rf_evidence').execute(
      { project, req, claim: '仅仿真，不代表实机验证', level: 'simulated', note: '回归测试：验证 Beta 不得被当成可发布' },
      exec,
    );
    assert.equal(simulated.ok, true, simulated.text);
  }
  const betaAudited = await tools.get('rf_audit').execute({ project }, exec);
  assert.equal(betaAudited.data.stats.errors, 0, 'simulated evidence alone leaves no blocking error');
  assert.match(betaAudited.data.verdict, /Beta/, 'low coverage still yields a Beta verdict');
  assert.equal(betaAudited.ok, false, 'Beta verdict must never be reported as publishable');

  const betaPackage = await tools.get('rf_package').execute({ project, beta: true }, exec);
  assert.equal(betaPackage.ok, true, betaPackage.text);
  assert.equal(betaPackage.data.release_level, 'beta', betaPackage.text);
  assert.match(betaPackage.data.sha256, /^[0-9a-f]{64}$/);
  assert.ok(readFileSync(betaPackage.data.path).subarray(0, 2).toString() === 'PK', 'package is a real zip');

  for (const req of ['REQ-004', 'REQ-005', 'REQ-006']) {
    const manual = await tools.get('rf_evidence').execute(
      { project, req, claim: '回归测试：人工复核已完成', level: 'manual', note: '回归测试模拟用户按 docs/06 操作' },
      exec,
    );
    assert.equal(manual.ok, true, manual.text);
  }
  const noReview = await tools.get('rf_audit').execute({ project }, exec);
  assert.equal(noReview.data.review.valid, false, 'a packet without a recorded verdict is not a review');
  assert.equal(noReview.data.release_level, 'beta', noReview.text);

  const recorded = await tools.get('rf_review').execute(
    { project, verdict: 'pass', score: 90, reviewer: 'host-test reviewer', findings: [] },
    exec,
  );
  assert.equal(recorded.data.review.valid, true, recorded.text);
  assert.ok(readFileSync(join(project, 'forge', 'review.json'), 'utf8').includes('host-test reviewer'));

  const released = await tools.get('rf_audit').execute({ project }, exec);
  assert.equal(released.data.release_level, 'release', released.text);
  assert.equal(released.ok, true, released.text);
  const releasePackage = await tools.get('rf_package').execute({ project }, exec);
  assert.equal(releasePackage.ok, true, releasePackage.text);
  assert.equal(releasePackage.data.release_level, 'release', releasePackage.text);

  const manualNoNote = await tools.get('rf_evidence').execute(
    { project, req: 'REQ-005', claim: '没有记录谁在何时如何确认', level: 'manual' },
    exec,
  );
  assert.equal(manualNoNote.ok, false, 'manual evidence without a note is rejected at the tool boundary');
  assert.match(manualNoNote.text, /note/);

  const missingReq = await tools.get('rf_evidence').execute(
    { project, req: 'REQ-999', claim: '不存在的需求', level: 'assumed' },
    exec,
  );
  assert.equal(missingReq.ok, false, 'evidence for an unknown requirement is rejected');
  assert.match(missingReq.text, /需求不存在/);

  const evidence = await tools.get('rf_evidence').execute(
    { project, req: 'REQ-004', claim: '在 30cm 处停住', level: 'manual', note: '测试脚本模拟' },
    exec,
  );
  assert.equal(evidence.ok, true, evidence.text);
  assert.match(evidence.text, /E-/);

  const verifyPath = join(project, 'forge', 'verify.yaml');
  const originalVerify = readFileSync(verifyPath, 'utf8');
  writeFileSync(
    verifyPath,
    originalVerify +
      '\n  - id: cwd-check\n    name: cwd 生效检查\n    run: python -m pytest tests -q\n    cwd: software\n    required: true\n    timeout: 60\n',
  );
  const cwdChecked = await tools.get('rf_check').execute({ project }, exec);
  assert.equal(cwdChecked.ok, true, cwdChecked.text);
  const cwdVerified = await tools.get('rf_verify').execute({ project }, exec);
  const cwdRow = cwdVerified.data.results.find((row) => row.id === 'cwd-check');
  assert.ok(cwdRow, cwdVerified.text);
  assert.equal(cwdRow.status, 'pass', cwdVerified.text);
  assert.equal(cwdVerified.data.failures, 0, cwdVerified.text);

  writeFileSync(
    verifyPath,
    originalVerify +
      '\n  - id: empty-check\n    name: 空跑检查\n    run: true\n    required: false\n',
  );
  const trivialChecked = await tools.get('rf_check').execute({ project }, exec);
  assert.equal(trivialChecked.ok, false, 'a no-op verify command must fail check');
  assert.ok(trivialChecked.data.check.stats.errors > 0, trivialChecked.text);
  assert.match(trivialChecked.text, /空跑/);

  writeFileSync(verifyPath, originalVerify);
  const cleanChecked = await tools.get('rf_check').execute({ project }, exec);
  assert.equal(cleanChecked.ok, true, cleanChecked.text);
  const cleanVerified = await tools.get('rf_verify').execute({ project }, exec);
  assert.equal(cleanVerified.ok, true, cleanVerified.text);

  writeFileSync(
    verifyPath,
    originalVerify +
      '\n  - id: optional-fail\n    name: 可选命令失败检查\n    run: python -c "raise SystemExit(1)"\n    required: false\n',
  );
  const optionalFailed = await tools.get('rf_verify').execute({ project }, exec);
  assert.equal(optionalFailed.ok, false, 'an optional command that ran and failed is still a failure');
  assert.ok(optionalFailed.data.failures >= 1, optionalFailed.text);
  const optionalRow = optionalFailed.data.results.find((row) => row.id === 'optional-fail');
  assert.equal(optionalRow.status, 'fail', optionalFailed.text);

  writeFileSync(verifyPath, originalVerify);
  const restoredChecked = await tools.get('rf_check').execute({ project }, exec);
  assert.equal(restoredChecked.ok, true, restoredChecked.text);
  const restoredVerified = await tools.get('rf_verify').execute({ project }, exec);
  assert.equal(restoredVerified.ok, true, restoredVerified.text);

  const partial = await tools.get('rf_verify').execute({ project, only: 'software-tests' }, exec);
  assert.equal(partial.ok, false, 'a subset verify must not report full success');
  assert.equal(partial.data.partial, true, partial.text);
  assert.match(partial.text, /只跑了子集/);

  const protocolPath = join(project, 'software', 'robotd', 'protocol.py');
  writeFileSync(protocolPath, readFileSync(protocolPath, 'utf8') + '\n# changed after verify\n');
  const staleAudited = await tools.get('rf_audit').execute({ project }, exec);
  assert.equal(staleAudited.ok, false, 'measured evidence goes stale after source changes');
  assert.match(staleAudited.text, /过期/);
} finally {
  dispose();
  assert.equal(tools.size, 0, 'dispose unregisters every tool');
  rmSync(temp, { recursive: true, force: true });
}
console.log('robot-forge DSH host test passed');
