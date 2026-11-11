/** Run the bundled Python forgekit and locate the current project. */
import { spawn } from 'node:child_process';
import { existsSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const PACKAGE_ROOT = dirname(HERE);
export const SKILL_ROOT = join(PACKAGE_ROOT, 'skills', 'robot-forge');
export const FORGE_SCRIPT = join(SKILL_ROOT, 'scripts', 'forge.py');

/** Return true when a directory is a robot-forge project root. */
function isProject(dir) {
  try {
    return statSync(join(dir, 'forge', 'robot.yaml')).isFile();
  } catch {
    return false;
  }
}

/** Resolve the project root from an explicit path, session cwd, or one child project. */
export function findProject(start) {
  let dir = resolve(start || process.cwd());
  for (let i = 0; i < 40; i += 1) {
    if (isProject(dir)) return dir;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  const base = resolve(start || process.cwd());
  try {
    const children = readdirSync(base, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
      .map((entry) => join(base, entry.name))
      .filter(isProject);
    if (children.length === 1) return children[0];
  } catch {
    // An unreadable cwd is reported by the tool as "no project" instead.
  }
  return null;
}

/** Resolve a tool's project argument, defaulting to the calling session's cwd. */
export function projectFrom(args, exec) {
  const explicit = args?.project;
  if (typeof explicit === 'string' && explicit.trim()) {
    const root = resolve(explicit.trim());
    return isProject(root) ? root : null;
  }
  const cwd = exec?.agent?.session?.cwd || process.cwd();
  return findProject(cwd);
}

/** Python launchers in preference order. */
function pythonLaunchers() {
  const configured = process.env.ROBOT_FORGE_PYTHON;
  if (configured) return [{ command: configured, prefix: [] }];
  return [
    { command: 'python', prefix: [] },
    { command: 'python3', prefix: [] },
    { command: 'py', prefix: ['-3'] },
  ];
}

function scriptFor(project) {
  // Always use the bundle's own engine: tool JSON is a bundle contract and must
  // not depend on an older vendored copy inside a generated project.
  return { script: FORGE_SCRIPT, cwd: project || process.cwd() };
}

function spawnOnce(command, argv, options) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, argv, {
      cwd: options.cwd,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
        PYTHONUTF8: '1',
        NO_COLOR: '1',
      },
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      options.signal?.removeEventListener('abort', onAbort);
      resolvePromise(value);
    };
    const onAbort = () => {
      child.kill();
      finish({ code: 130, stdout, stderr: stderr + '\n[aborted]' });
    };
    const timer = setTimeout(() => {
      child.kill();
      finish({ code: 124, stdout, stderr: stderr + '\n[timeout]' });
    }, options.timeoutMs);
    if (options.signal?.aborted) {
      onAbort();
      return;
    }
    options.signal?.addEventListener('abort', onAbort, { once: true });
    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => {
      stdout += chunk;
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk;
    });
    child.on('error', (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      options.signal?.removeEventListener('abort', onAbort);
      rejectPromise(error);
    });
    child.on('close', (code) => finish({ code: code ?? 1, stdout, stderr }));
  });
}

/** Run forge.py; falls back to python3/py only when the launcher is missing. */
export async function runForge({ project, args, cwd, signal, timeoutMs = 120000 }) {
  const target = scriptFor(project);
  const argvBase = project ? ['--project', project, ...args] : [...args];
  let lastError;
  for (const launcher of pythonLaunchers()) {
    try {
      const result = await spawnOnce(launcher.command, [...launcher.prefix, target.script, ...argvBase], {
        cwd: cwd || target.cwd,
        signal,
        timeoutMs,
      });
      return { ...result, command: [launcher.command, ...launcher.prefix, target.script, ...argvBase].join(' ') };
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
      lastError = error;
    }
  }
  throw new Error(
    '找不到 Python。请安装 Python 3.10+ 并加入 PATH，或设置 ROBOT_FORGE_PYTHON 指向解释器。' +
      (lastError ? ' (' + lastError.message + ')' : ''),
  );
}

/** Run and parse a JSON command. Exit 1 is returned as data; exit 2 is an error. */
export async function runForgeJson(options) {
  const result = await runForge(options);
  const text = result.stdout.trim();
  if (!text) {
    throw new Error(
      'forge.py 没有返回 JSON（exit ' + result.code + '）：' + (result.stderr.trim() || result.stdout.trim()),
    );
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    const start = text.indexOf('{');
    if (start >= 0) {
      try {
        data = JSON.parse(text.slice(start));
      } catch {
        // Fall through to the diagnostic below.
      }
    }
    if (data === undefined) {
      throw new Error('forge.py 输出不是 JSON（exit ' + result.code + '）：' + text.slice(-800));
    }
  }
  if (result.code === 2) {
    throw new Error((data && (data.error || data.reason)) || result.stderr.trim() || 'forge.py 内部错误');
  }
  return { data, code: result.code, stderr: result.stderr, command: result.command };
}

/** Format a short issue list for the model-facing text. */
export function issueLines(issues, limit = 8) {
  const rows = Array.isArray(issues) ? issues : [];
  return rows
    .slice(0, limit)
    .map((issue) => {
      const where = issue.file ? ' (' + issue.file + ')' : '';
      return '- [' + issue.level + '] ' + issue.rule + ' ' + issue.msg + where;
    })
    .join('\n');
}
