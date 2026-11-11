/** Model-facing robot-forge tools over the bundled Python gate engine. */
import { resolve } from 'node:path';
import { issueLines, projectFrom, runForge, runForgeJson } from './run.js';

const OUTPUT = {
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    text: { type: 'string' },
    data: { type: 'object' },
  },
  required: ['ok', 'text'],
};

function render(_args, value) {
  return [{ type: 'text', text: value.text }];
}

function ok(text, data) {
  return { ok: true, text, data: data || {} };
}

function fail(text, data) {
  return { ok: false, text, data: data || {} };
}

function wrap(error) {
  const message = error instanceof Error ? error.message : String(error);
  return fail('robot-forge 执行失败：' + message, { error: message });
}

const PROJECT = {
  type: 'string',
  description: '项目根目录（含 forge/robot.yaml）。省略时从会话工作目录向上找，或找唯一子项目。',
};

function projectText(root) {
  return root
    ? '项目：' + root
    : '当前目录不在 robot-forge 项目里。先调用 rf_blueprints 选最近蓝本，再 rf_new 创建，或把 project 指到项目根目录。';
}

function checkTool() {
  return {
    name: 'rf_check',
    description:
      '重新生成派生产物（BOM、接线、电源、图、文档块），再跑结构/一致性检查，最后返回唯一下一步。' +
      '改完 forge/robot.yaml 或文档后必须调用。错误未清零不要继续。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        deep: { type: 'boolean', description: '发布前深检：把必须项缺证据升级为错误。' },
        render: { type: 'boolean', description: 'false 时只检查，不重新生成（默认 true）。' },
      },
      additionalProperties: false,
    },
    timeoutMs: 180000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        if (args.render !== false) {
          const rendered = await runForge({ project: root, args: ['render'], signal: exec.signal, timeoutMs: 120000 });
          if (rendered.code !== 0) {
            return fail('重新生成失败（exit ' + rendered.code + '）：\n' + (rendered.stderr || rendered.stdout).slice(-1200));
          }
        }
        const checkArgs = ['check', '--json'];
        if (args.deep) checkArgs.push('--deep');
        const check = await runForgeJson({ project: root, args: checkArgs, signal: exec.signal, timeoutMs: 120000 });
        const next = await runForgeJson({ project: root, args: ['next', '--json'], signal: exec.signal });
        const stats = check.data.stats || {};
        const lines = [
          'robot-forge check：' + (stats.errors || 0) + ' 错误 / ' + (stats.warnings || 0) + ' 警告',
          projectText(root),
        ];
        const issues = issueLines(check.data.issues || []);
        if (issues) lines.push(issues);
        lines.push('下一步：' + (next.data.tool || '') + ' — ' + (next.data.reason || ''));
        return {
          ok: (stats.errors || 0) === 0,
          text: lines.join('\n'),
          data: { check: check.data, next: next.data },
        };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge check', kind: 'other', rawInput: args }),
  };
}

function verifyTool() {
  return {
    name: 'rf_verify',
    description:
      '执行 forge/verify.yaml 的验证命令，记录证据并刷新验收报告。这是唯一能产生“实测通过”的方式；' +
      '退出码 0 才算通过。长命令会等到结束。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        only: { type: 'string', description: '只跑这些命令 id，逗号分隔。' },
        record: { type: 'boolean', description: 'false 时不写证据（默认 true）。' },
      },
      additionalProperties: false,
    },
    timeoutMs: 900000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const cmd = ['verify', '--json'];
        if (args.only) cmd.push('--only', String(args.only));
        if (args.record === false) cmd.push('--no-record');
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal, timeoutMs: 900000 });
        const data = result.data;
        const rows = (data.results || []).map((row) => {
          const label = row.status === 'pass' ? 'PASS' : row.status === 'skip' ? 'SKIP' : 'FAIL';
          return '  ' + label + '  ' + row.id + (row.exit === undefined || row.exit === null ? '' : ' (exit ' + row.exit + ')');
        });
        const head = data.partial
          ? 'rf_verify：只跑了子集，不能声称全部通过；未跑：' + (data.omitted_required || []).join(', ') +
            (data.failures ? '；另有 ' + data.failures + ' 条失败' : '')
          : data.ok
            ? 'rf_verify：全部必需验证通过' + (data.skipped ? '（跳过 ' + data.skipped + ' 条非必需）' : '')
            : 'rf_verify：' + data.failures + ' 条必需验证失败';
        const next = data.next ? '\n下一步：' + (data.next.tool || '') + ' — ' + (data.next.reason || '') : '';
        const evidence = data.evidence_ids?.length ? '\n本次记录证据 ' + data.evidence_ids.length + ' 条。' : '';
        return { ok: Boolean(data.ok), text: head + '\n' + rows.join('\n') + evidence + next, data };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge verify', kind: 'other', rawInput: args }),
  };
}

function auditTool() {
  return {
    name: 'rf_audit',
    description:
      '发布审计：评分、must 需求证据覆盖、未验证项。只有这里通过，才能说“可以发布”；' +
      '否则只能按返回的结论标 Beta 并列出未验证项。',
    parameters: {
      type: 'object',
      properties: { project: PROJECT },
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const result = await runForgeJson({ project: root, args: ['audit', '--json'], signal: exec.signal });
        const data = result.data;
        const req = data.requirements || {};
        const issues = issueLines((data.issues || []).filter((issue) => issue.level === 'error'));
        const text = [
          'rf_audit：' + data.score + '/100 · ' + data.verdict,
          'must 覆盖 ' + (req.covered || 0) + '/' + (req.must || 0) + '（' + (req.coverage || 0) + '%）· 证据 ' + (data.evidence || 0) + ' 条',
          issues,
          data.next ? '下一步：' + data.next.tool + ' — ' + data.next.reason : '',
        ]
          .filter(Boolean)
          .join('\n');
        return { ok: data.verdict === '可以发布', text, data };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge audit', kind: 'other', rawInput: args }),
  };
}

function statusTool() {
  return {
    name: 'rf_status',
    description: '一页看完项目状态：预算、元件、must 证据分布、检查错误、最近证据、唯一下一步。开始工作前先调用。',
    parameters: {
      type: 'object',
      properties: { project: PROJECT },
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const result = await runForgeJson({ project: root, args: ['status', '--json'], signal: exec.signal });
        const data = result.data;
        const levels = Object.entries(data.must_levels || {})
          .map(([key, value]) => key + '=' + value)
          .join('  ');
        const text = [
          data.name + ' v' + data.version + ' · ' + data.gear,
          '预算 ¥' + data.budget_cny + '（清单 ¥' + data.total_cost_cny + '）· ' + data.components + ' 个元件',
          'must 证据：' + (levels || '无') + ' · 检查 ' + data.check.errors + ' 错误 / ' + data.check.warnings + ' 警告',
          data.next ? '下一步：' + data.next.tool + ' — ' + data.next.reason : '',
        ]
          .filter(Boolean)
          .join('\n');
        return ok(text, data);
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge status', kind: 'other', rawInput: args }),
  };
}

function blueprintsTool() {
  return {
    name: 'rf_blueprints',
    description:
      '列出内置蓝本、预算、工期、难度和适用形态。蓝本只是已验证的起点，不是形态白名单；' +
      '没有完全匹配时按 references/blueprints.md §3 从最近蓝本派生（任意形态都走同一套契约）。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    timeoutMs: 60000,
    output: { schema: OUTPUT, render },
    async execute(_args, exec) {
      try {
        const result = await runForgeJson({ args: ['blueprints', '--json'], signal: exec.signal });
        const rows = (result.data.blueprints || []).map(
          (bp) =>
            '- ' + bp.id + ' · ' + bp.name + ' · ¥' + bp.cost_cny + ' · ' + bp.time + ' · ' + bp.one_liner,
        );
        return ok(
          '可用蓝本：\n' +
            rows.join('\n') +
            '\n\n蓝本只是起点，不是形态白名单；没有完全匹配时选最近蓝本，按 references/blueprints.md §3 的 freeform 协议改造（任意形态都走同一套契约）。',
          result.data,
        );
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge blueprints', kind: 'other', rawInput: args }),
  };
}

function newTool() {
  return {
    name: 'rf_new',
    description:
      '用蓝本创建一个完整可运行项目：机器人项目骨架、forge 状态层、文档、软件/固件/仿真模板。' +
      '先调用 rf_blueprints 选最近起点；blueprint 必填。创建后立刻读生成项目的 README 和 docs/00-总览.md。',
    parameters: {
      type: 'object',
      properties: {
        name: { type: 'string', description: '项目中文名。' },
        blueprint: {
          type: 'string',
          description:
            '蓝本 id（先运行 rf_blueprints）；没有完全匹配就选最近起点，生成后按 references/blueprints.md §3 的 freeform 协议改造。',
        },
        slug: { type: 'string', description: '目录名/仓库名（小写连字符）；省略时自动生成。' },
        dir: { type: 'string', description: '父目录；省略时用会话工作目录，在其下创建 <slug>。' },
      },
      required: ['name', 'blueprint'],
      additionalProperties: false,
    },
    timeoutMs: 180000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const name = String(args.name || '').trim();
        if (!name) return fail('name 不能为空。');
        const blueprint = String(args.blueprint || '').trim();
        if (!blueprint) {
          return fail('blueprint 必填：先调用 rf_blueprints 选最近起点；没有完全匹配时按 freeform 协议改造。');
        }
        const cwd = args.dir ? resolve(args.dir) : exec?.agent?.session?.cwd || process.cwd();
        const cmd = ['new', name, '--json', '--blueprint', blueprint];
        if (args.slug) cmd.push('--slug', String(args.slug));
        const result = await runForgeJson({ args: cmd, cwd, signal: exec.signal, timeoutMs: 120000 });
        const data = result.data;
        const text = [
          '已创建 ' + data.project,
          '蓝本 ' + data.blueprint + ' · ' + data.components + ' 个元件 · 预算 ¥' + data.budget_cny,
          '下一步：' + (data.next?.tool || 'rf_check') + ' — ' + (data.next?.reason || ''),
          '先读 ' + data.project + '/README.md、docs/00-总览.md 和 forge/robot.yaml，再按 wish 改造。',
        ].join('\n');
        return ok(text, data);
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge new', kind: 'other', rawInput: args }),
  };
}

function evidenceTool() {
  return {
    name: 'rf_evidence',
    description:
      '记录人工证据（用户试用、目视检查、装配确认）。只能在人真的确认后调用；' +
      '不能把模型猜测写成 manual。assumed/simulated 不计入发布覆盖。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        req: { type: 'string', description: '需求 id，如 REQ-004。' },
        claim: { type: 'string', description: '证明了什么，写具体观察。' },
        level: {
          type: 'string',
          enum: ['manual', 'simulated', 'assumed'],
          description: 'manual=人确认；simulated=仿真；assumed=假设，不算验证。',
        },
        note: { type: 'string', description: '谁在什么时候怎么确认的。' },
        artifact: { type: 'string', description: '截图/日志等证据文件的相对路径。' },
      },
      required: ['claim'],
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const claim = String(args.claim || '').trim();
        if (!claim) return fail('claim 不能为空：写清谁在什么条件下确认了什么。');
        const level = String(args.level || 'manual');
        if (level === 'manual' && !String(args.note || '').trim()) {
          return fail('manual 证据必须写 note：谁、在哪台实物上、按什么步骤确认。');
        }
        const cmd = ['evidence', '--json', '--claim', claim];
        if (args.req) cmd.push('--req', String(args.req));
        if (args.level) cmd.push('--level', level);
        if (args.note) cmd.push('--note', String(args.note));
        if (args.artifact) cmd.push('--artifact', String(args.artifact));
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal });
        const row = result.data.evidence || {};
        return ok(
          '已记录 ' + row.id + '（' + row.level + '）' + (row.req ? ' → ' + row.req : '') + '\n' + row.claim,
          result.data,
        );
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge evidence', kind: 'other', rawInput: args }),
  };
}

function intakeTool() {
  return {
    name: 'rf_intake',
    description:
      '把一句自然语言愿望解析成工程订单：12 类形态中最近的一类、预算/档位/域、默认假设、最多 3 个会改变设计的问题、安全旗标与合规红线。' +
      '有违法/伤害用途时直接拒绝并给安全替代。用户说不清需求时先调用它，不要自己猜形态。',
    parameters: {
      type: 'object',
      properties: {
        text: { type: 'string', description: '用户的原始愿望，尽量保留原话。' },
        budget: { type: 'number', description: '预算（元）；用户没说就省略。' },
      },
      required: ['text'],
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const text = String(args.text || '').trim();
        if (text.length < 4) return fail('text 太短：至少写清“谁在什么场景用它做什么”。');
        const cmd = ['intake', text, '--json'];
        if (args.budget !== undefined) cmd.push('--budget', String(args.budget));
        const result = await runForgeJson({ args: cmd, signal: exec.signal });
        const data = result.data;
        if (data.allowed === false) {
          return fail(
            data.error + '\n安全替代：\n' + (data.safe_alternatives || []).map((x) => '  - ' + x).join('\n'),
            data,
          );
        }
        const questions = (data.questions || []).map(
          (q) => '  ? ' + q.question + '\n    默认：' + q.default,
        );
        const flags = (data.safety || []).map((f) => '  - ' + f.title + '：' + f.requirement);
        const textOut = [
          '形态：' + data.archetype_name + '（' + data.archetype + '，置信度 ' + data.confidence + '）',
          '蓝本：' + data.blueprint + ' ｜ 预算：' + data.budget_cny + ' 元（' + data.budget_source + '）｜ 档位：' + data.gear,
          '域：' + (data.domains || []).join(' / '),
          '一句话：' + data.one_liner,
          flags.length ? '安全旗标：\n' + flags.join('\n') : '',
          questions.length ? '至多三个会改变设计的问题：\n' + questions.join('\n') : '',
          '下一步：' + (data.next?.tool || 'rf_new') + ' — ' + (data.next?.reason || '选蓝本创建项目'),
        ]
          .filter(Boolean)
          .join('\n');
        return ok(textOut, data);
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge intake', kind: 'other', rawInput: args }),
  };
}

function designTool() {
  return {
    name: 'rf_design',
    description:
      '全栈工程核算：扭矩/转速余量、各电源轨电流与续航、C-rate、线径、散热密度、成本与超支项；' +
      'write=true 写 forge/design.md。选型或机械参数改过就重跑，别凭感觉说“够用”。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        write: { type: 'boolean', description: '把核算与发现写进 forge/design.md（默认 true）。' },
      },
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const cmd = ['design', '--json'];
        if (args.write !== false) cmd.push('--write');
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal });
        const data = result.data;
        const t = data.torque || {};
        const pw = data.power || {};
        const cost = data.cost || {};
        const findings = (data.findings || []).map((f) => '  [' + f.level + '] ' + f.rule + ' ' + f.msg);
        const textOut = [
          '设计核算：' + (data.ok ? '无阻断' : '有阻断'),
          '扭矩：需要 ' + t.required_kgcm + ' kg·cm ｜ 现有 ' + t.available_kgcm + ' ｜ 余量 ' + t.margin,
          '电源：' + pw.source_voltage_v + ' V ｜ 续航 ' + pw.runtime_h + ' h ｜ 持续 ' + pw.continuous_current_a +
            ' A / 峰值 ' + pw.peak_current_a + ' A ｜ ' + pw.c_rate + ' C',
          '成本：' + cost.total_cny + ' / ' + cost.budget_cny + ' 元（' + cost.used_pct + '%）',
          findings.length ? '发现：\n' + findings.join('\n') : '发现：无',
          data.path ? '已写入：' + data.path : '',
        ]
          .filter(Boolean)
          .join('\n');
        return { ok: Boolean(data.ok), text: textOut, data };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge design', kind: 'other', rawInput: args }),
  };
}

function traceTool() {
  return {
    name: 'rf_trace',
    description:
      '生成需求追踪矩阵：每条 must/should/nice 需求 → 验证命令 → 证据 → 等级 → 是否闭环。' +
      'write=true 写 forge/trace.md；交付前必须有一条 must 全覆盖的 trace。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        write: { type: 'boolean', description: '写入 forge/trace.md（默认 true）。' },
      },
      additionalProperties: false,
    },
    timeoutMs: 120000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const cmd = ['trace', '--json'];
        if (args.write !== false) cmd.push('--write');
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal });
        const data = result.data;
        const rows = (data.rows || []).map(
          (r) => '  ' + r.id + ' [' + r.priority + '] ' + (r.ok ? '闭环' : '未闭环') + ' · ' + r.level + ' · ' + (r.verify || '-'),
        );
        const textOut = [
          'must 覆盖：' + (data.covered || 0) + '/' + (data.must || 0) + '（' + (data.coverage || 0) + '%）',
          rows.join('\n'),
          data.path ? '已写入：' + data.path : '',
          data.ok ? '' : '仍有未闭环的 must 需求：不能用“做完了”交付。',
        ]
          .filter(Boolean)
          .join('\n');
        return { ok: Boolean(data.ok), text: textOut, data };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge trace', kind: 'other', rawInput: args }),
  };
}

function reviewTool() {
  return {
    name: 'rf_review',
    description:
      '生成独立盲审包 forge/review-packet.md/json：复现命令、需求追踪、最近证据、机器发现、四副眼镜评审模板。' +
      '评审由没有参与实现的代理或人完成后，由 Lead 用 verdict/score/reviewer/findings 记录 forge/review.json（不许实现者自评）；' +
      '只有有效的 pass 且 score>=70 才允许 audit 判 release。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        write: { type: 'boolean', description: '写 review-packet.md/json（默认 true）。' },
        verdict: { type: 'string', enum: ['pass', 'needs_revision', 'reject'], description: '独立评审结论；不传则只生成盲审包。' },
        score: { type: 'number', minimum: 0, maximum: 100, description: '评审分数 0–100；release 要求 pass 且 >=70。' },
        reviewer: { type: 'string', description: '评审者名字（人/独立代理），记录结论时必填。' },
        note: { type: 'string', description: '评审备注。' },
        findings: {
          type: 'array',
          description: '评审发现物；每条含 id/severity/file/problem/required_fix/evidence。',
          items: { type: 'object', additionalProperties: true },
        },
      },
      additionalProperties: false,
    },
    timeoutMs: 180000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const cmd = ['review', '--json'];
        if (args.write === false) cmd.push('--no-write');
        if (args.verdict) cmd.push('--verdict', String(args.verdict));
        if (args.score !== undefined && args.score !== null) cmd.push('--score', String(args.score));
        if (args.reviewer) cmd.push('--reviewer', String(args.reviewer));
        if (args.note) cmd.push('--note', String(args.note));
        if (args.findings !== undefined) cmd.push('--findings', JSON.stringify(args.findings));
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal });
        const data = result.data;
        const focus = (data.focus || []).slice(0, 5).map((x) => '  - ' + x);
        const textOut = [
          '盲审包：' + (data.ok ? '可交付评审' : '仍有阻断/未闭环'),
          '结论：' + data.verdict + '（' + data.score + ' 分）｜ 错误 ' + data.errors + ' ｜ 警告 ' + data.warnings +
            ' ｜ must 覆盖 ' + data.coverage + '%',
          data.path ? '文件：' + data.path : '',
          focus.length ? '优先核对：\n' + focus.join('\n') : '',
          data.review && data.review.reason ? '评审状态：' + data.review.reason : '',
          '下一步：把 packet 交给独立评审者，按四副眼镜出 findings；记录 pass 后才能 audit release。',
        ]
          .filter(Boolean)
          .join('\n');
        return { ok: Boolean(data.ok), text: textOut, data };
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge review', kind: 'other', rawInput: args }),
  };
}

function packageTool() {
  return {
    name: 'rf_package',
    description:
      '发布打包：先跑发布审计，0 错误且 must 全覆盖才允许 release；否则拒绝，加 beta=true 只生成 Beta 包。' +
      '产物含逐文件 SHA256 的 RELEASE.json 与 SHA256SUMS；这是“可交付”的唯一凭据。',
    parameters: {
      type: 'object',
      properties: {
        project: PROJECT,
        out: { type: 'string', description: '输出目录（默认 dist）。' },
        beta: { type: 'boolean', description: '审计未达 release 时仍打 Beta 包（明确标注未验证项）。' },
      },
      additionalProperties: false,
    },
    timeoutMs: 300000,
    output: { schema: OUTPUT, render },
    async execute(args, exec) {
      try {
        const root = projectFrom(args, exec);
        if (!root) return fail(projectText(root));
        const cmd = ['package', '--json'];
        if (args.out) cmd.push('--out', String(args.out));
        if (args.beta) cmd.push('--beta');
        const result = await runForgeJson({ project: root, args: cmd, signal: exec.signal });
        const data = result.data;
        if (data.ok === false) {
          const reasons = (data.blockers || data.errors || []).map((x) => '  - ' + (typeof x === 'string' ? x : x.msg || JSON.stringify(x)));
          return fail(
            '打包被拒绝：' + (data.error || data.reason || '发布审计未通过') +
              (reasons.length ? '\n' + reasons.join('\n') : ''),
            data,
          );
        }
        return ok(
          '已生成 ' + (data.release_level || 'release') + ' 包：' + data.path + '\nSHA256 ' + data.sha256 + '\n' +
            '包含 ' + (data.files || 0) + ' 个文件；RELEASE.json 记录逐文件哈希与评分。',
          data,
        );
      } catch (error) {
        return wrap(error);
      }
    },
    presentCall: (args) => ({ card: 'generic', title: 'robot-forge package', kind: 'other', rawInput: args }),
  };
}

/** Build one fresh definition set per plugin activation. */
export function createTools() {
  return [
    intakeTool(),
    blueprintsTool(),
    newTool(),
    statusTool(),
    checkTool(),
    designTool(),
    verifyTool(),
    auditTool(),
    traceTool(),
    reviewTool(),
    packageTool(),
    evidenceTool(),
  ];
}
