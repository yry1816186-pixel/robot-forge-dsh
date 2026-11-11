/**
 * Robot Forge for DeepSeek Harness.
 *
 * Host half: twelve model-facing tools over the bundled Python gate engine,
 * one compact prompt section, and an optional /forge human command. The Skill
 * itself is mounted by this bundle's cordis.patch.yml through
 * @deepseek-ai/dsh-skill-filesystem, so the instruction body stays on disk and
 * is loaded only when the model asks for it.
 */
import { createTools } from './lib/tools.js';
import { findProject, issueLines, runForge, runForgeJson } from './lib/run.js';

export const name = 'robot-forge';
export const inject = ['tools', 'systemPrompt'];

const GUIDANCE = [
  'Robot Forge 是机器人项目的门禁层。用户提出机器人、硬件、固件、结构或“做一个实物”的需求时，先加载 robot-forge skill，再按七阶段工作：接单→定案→架构→建造→证明→盲审→发布。',
  '形态不限：桌面、轮式、机械臂、四足/双足/人形、飞行、水下、爬壁、工业专机、纯传感节点都可以；12 类配方只是起点，不是形态白名单。',
  '接单先 rf_intake 解析愿望（形态/预算/默认假设/≤3 个问题/安全旗标）；再 rf_blueprints 选最近蓝本、rf_new 创建；rf_design 做扭矩/功耗/续航/线径/散热/成本核算；rf_check 生成并检查；rf_verify 跑真实命令并记证据；rf_trace 出需求追踪矩阵；rf_review 出盲审包并由 Lead 记录独立评审结论；rf_audit 要求有效盲审 pass 才 release；rf_package 才允许打包发布。',
  '只有用户真实试用后才能用 rf_evidence 记 manual；模型不得替用户填写人工证据。simulated/assumed 不计入发布覆盖。',
  '没有新鲜 rf_verify 证据不要声称“实测通过”；没有有效 review.json 的 pass 或 rf_audit 不通过，不要声称“可以发布”；没有实物的部分明确标未验证。',
  '安全旗标（锂电/市电/运动/激光/隐私/联网/儿童/户外/医疗）必须落到 docs/07 与 compliance 块；违法或伤害用途直接拒绝并给安全替代。',
  '复杂项目可用 DSH 子代理按域并行（硬件/固件/软件/仿真/文档），但 forge/robot.yaml 是唯一真相源，写作用域不得重叠，Lead 负责合并与最终 rf_check。',
  '不要把 rf_* 换成 shell 命令：工具会返回结构化问题和唯一下一步。',
].join('\n');

function forgeCommand() {
  return {
    name: 'forge',
    description: '查看 robot-forge 项目状态或下一步（不打扰模型）',
    input: { hint: 'status | next | check' },
    async handler({ agent, rawInput, signal }) {
      const cwd = agent?.session?.cwd || process.cwd();
      const root = findProject(cwd);
      if (!root) {
        return {
          kind: 'error',
          text: '当前目录不在 robot-forge 项目里。先 rf_blueprints 选最近蓝本，再 rf_new 创建；或先进入项目根目录。',
        };
      }
      const sub = (rawInput || '').trim().toLowerCase() || 'status';
      try {
        if (sub === 'check') {
          const rendered = await runForge({ project: root, args: ['render'], signal });
          if (rendered.code !== 0) return { kind: 'error', text: '重新生成失败：' + (rendered.stderr || '').slice(-800) };
          const checked = await runForgeJson({ project: root, args: ['check', '--json'], signal });
          const stats = checked.data.stats || {};
          const issues = issueLines(checked.data.issues || [], 10);
          return {
            kind: stats.errors ? 'error' : 'success',
            text:
              'robot-forge check：' + (stats.errors || 0) + ' 错误 / ' + (stats.warnings || 0) + ' 警告' +
              (issues ? '\n' + issues : ''),
          };
        }
        const cmd = sub === 'next' ? ['next', '--json'] : ['status', '--json'];
        const result = await runForgeJson({ project: root, args: cmd, signal });
        if (sub === 'next') {
          return {
            kind: 'success',
            text: result.data.tool + ' — ' + result.data.reason + '\n' + (result.data.commands || []).join('\n'),
          };
        }
        const data = result.data;
        if (data.error) {
          return { kind: 'error', text: 'robot-forge 无法读取项目：' + data.error };
        }
        const levels = Object.entries(data.must_levels || {}).map(([key, value]) => key + '=' + value).join('  ');
        return {
          kind: data.ok ? 'success' : 'error',
          text:
            data.name + ' v' + data.version + ' · ' + data.gear + '\n' +
            '预算 ¥' + data.budget_cny + '（清单 ¥' + data.total_cost_cny + '）· ' + data.components + ' 个元件\n' +
            'must 证据：' + (levels || '无') + ' · 检查 ' + data.check.errors + ' 错误 / ' + data.check.warnings + ' 警告\n' +
            '下一步：' + (data.next?.tool || '') + ' — ' + (data.next?.reason || ''),
        };
      } catch (error) {
        return { kind: 'error', text: 'robot-forge：' + (error instanceof Error ? error.message : String(error)) };
      }
    },
  };
}

export function apply(ctx) {
  const disposers = [];
  for (const definition of createTools()) {
    disposers.push(ctx.tools.register(definition));
  }
  const section = ctx.systemPrompt.section({
    name: 'tool:robot-forge',
    order: 9500,
    text: GUIDANCE,
  });
  if (typeof section === 'function') disposers.push(section);

  const commands = ctx.get('commands');
  if (commands && typeof commands.register === 'function') {
    const dispose = commands.register(forgeCommand());
    if (typeof dispose === 'function') disposers.push(dispose);
  }

  return () => {
    for (const dispose of disposers.reverse()) {
      try {
        dispose();
      } catch {
        // Disposal is best-effort; the Loader owns the final state.
      }
    }
  };
}
