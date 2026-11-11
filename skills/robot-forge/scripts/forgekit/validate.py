"""Static validation of the DSH-native robot-forge bundle."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

PACKAGE_NAME = "robot-forge-dsh"
SKILL_NAME = "robot-forge"
SKILL_ALLOWED = {"name", "description", "whenToUse", "metadata", "disable-model-invocation", "user-invocable"}
REFERENCE_FILES = (
    "spec.md",
    "workflow.md",
    "quality.md",
    "blueprints.md",
    "stacks.md",
    "archetypes.md",
    "design.md",
    "compliance.md",
    "testing.md",
    "release.md",
    "orchestration.md",
)
FORBIDDEN_CACHE = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".ipynb_checkpoints"}
PLACEHOLDER_TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")
SKILL_BACKTICK_ARTIFACT = "\\`"


class Issue:
    def __init__(self, level, code, msg, path=""):
        self.level = level
        self.code = code
        self.msg = msg
        self.path = path

    def as_dict(self):
        return {"level": self.level, "code": self.code, "msg": self.msg, "path": str(self.path)}

    def __str__(self):
        where = (" " + str(self.path)) if self.path else ""
        return "[%s] %s %s%s" % (self.level.upper(), self.code, self.msg, where)


def _read(path):
    return path.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end].strip("\n")
    data = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and ":" in line:
            key, _, value = line.partition(":")
            data.setdefault("__nested__", {})[key.strip()] = value.strip().strip('"').strip("'")
            continue
        if line.startswith((" ", "\t")):
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, text[end + 4 :]


def _parse_yaml(text):
    try:
        import yaml
    except Exception:  # noqa: BLE001
        return None, "PyYAML 未安装，跳过 patch 结构解析"
    try:
        return yaml.safe_load(text.replace("!!js ", "")), ""
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _check_package(root, issues, versions):
    path = root / "package.json"
    if not path.is_file():
        issues.append(Issue("error", "P001", "缺少 package.json（DSH bundle 清单）", "package.json"))
        return
    try:
        data = json.loads(_read(path))
    except Exception as exc:  # noqa: BLE001
        issues.append(Issue("error", "P002", "package.json 不是合法 JSON：%s" % exc, "package.json"))
        return
    versions["package.json"] = str(data.get("version", ""))
    if data.get("name") != PACKAGE_NAME:
        issues.append(Issue("error", "P003", "package.json name 必须是 %s" % PACKAGE_NAME, "package.json"))
    if not re.match(r"^\d+\.\d+\.\d+$", str(data.get("version", ""))):
        issues.append(Issue("error", "P004", "version 必须是 x.y.z", "package.json"))
    if data.get("type") != "module":
        issues.append(Issue("error", "P005", "type 必须是 module（ESM Host 插件）", "package.json"))
    dsh = data.get("dsh") or {}
    bundle = dsh.get("bundle") or {}
    patch = str(bundle.get("patch", ""))
    if not patch:
        issues.append(Issue("error", "P006", "dsh.bundle.patch 缺失，DSH 不会加载这个 bundle", "package.json"))
    elif not (root / patch.lstrip("./")).is_file():
        issues.append(Issue("error", "P007", "dsh.bundle.patch 指向不存在的 %s" % patch, "package.json"))
    exports = data.get("exports") or {}
    if "." not in exports:
        issues.append(Issue("error", "P008", "exports 缺少 .（Host 插件入口）", "package.json"))
    if "./package.json" not in exports:
        issues.append(Issue("error", "P009", "exports 缺少 ./package.json（patch 需要用它解析包路径）", "package.json"))
    if "./icon" not in exports:
        issues.append(Issue("warn", "P010", "exports 缺少 ./icon，插件页会用默认图标", "package.json"))
    files = data.get("files") or []
    for required in ("index.js", "cordis.patch.yml", "skills"):
        if required not in files:
            issues.append(Issue("warn", "P011", "files 没有包含 %s；发布 npm 包时会缺文件" % required, "package.json"))


def _check_patch(root, issues):
    path = root / "cordis.patch.yml"
    if not path.is_file():
        issues.append(Issue("error", "P020", "缺少 cordis.patch.yml", "cordis.patch.yml"))
        return
    text = _read(path)
    data, problem = _parse_yaml(text)
    if problem:
        issues.append(Issue("error", "P021", "cordis.patch.yml 解析失败：%s" % problem, "cordis.patch.yml"))
    elif data is not None:
        rows = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("insert"), list):
                    rows.extend(item["insert"])
        names = [str(row.get("name", "")) for row in rows if isinstance(row, dict)]
        if PACKAGE_NAME not in names:
            issues.append(Issue("error", "P022", "patch 没有 insert %s" % PACKAGE_NAME, "cordis.patch.yml"))
        if "@deepseek-ai/dsh-skill-filesystem" not in names:
            issues.append(Issue("error", "P023", "patch 没有 insert skill-filesystem，技能不会出现在目录", "cordis.patch.yml"))
    for needle in ("bundledSkillDir", "createRequire(baseUrl)", "resolve('%s/package.json')" % PACKAGE_NAME):
        if needle not in text:
            issues.append(Issue("error", "P024", "patch 缺少 %s（包路径必须从 profile 解析）" % needle, "cordis.patch.yml"))


def _check_node_files(root, issues):
    for rel in ("index.js", "lib/tools.js", "lib/run.js"):
        path = root / rel
        if not path.is_file():
            issues.append(Issue("error", "P030", "缺少 %s" % rel, rel))
    node = shutil.which("node")
    if not node:
        issues.append(Issue("warn", "P031", "没有 node，跳过 JS 语法检查"))
        return
    for rel in ("index.js", "lib/tools.js", "lib/run.js"):
        path = root / rel
        if not path.is_file():
            continue
        result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            issues.append(Issue("error", "P032", "%s 语法错误：%s" % (rel, (result.stderr or result.stdout).strip()[:500]), rel))
    index = root / "index.js"
    if index.is_file():
        text = _read(index)
        for needle in ("export function apply", "export const inject", "rf_", "systemPrompt.section"):
            if needle not in text:
                issues.append(Issue("error", "P033", "index.js 缺少 %s" % needle, "index.js"))
    tools = root / "lib" / "tools.js"
    if tools.is_file():
        names = re.findall(r"name: '(rf_[a-z_]+)'", _read(tools))
        expected = {
            "rf_intake", "rf_blueprints", "rf_new", "rf_status", "rf_check", "rf_design",
            "rf_verify", "rf_audit", "rf_trace", "rf_review", "rf_package", "rf_evidence",
        }
        if set(names) != expected:
            issues.append(Issue("error", "P034", "工具集合不完整：%s" % sorted(set(names)), "lib/tools.js"))


def _check_display(root, issues):
    icon = root / "icon.svg"
    if not icon.is_file():
        issues.append(Issue("error", "P040", "缺少 icon.svg", "icon.svg"))
    elif icon.stat().st_size > 256 * 1024:
        issues.append(Issue("error", "P041", "icon.svg 超过 256 KiB", "icon.svg"))
    else:
        head = _read(icon)[:200].lstrip()
        if not (head.startswith("<svg") or head.startswith("<?xml")):
            issues.append(Issue("error", "P042", "icon.svg 不是 SVG", "icon.svg"))
    for lang in ("zh", "en"):
        path = root / "locale" / (lang + ".json")
        if not path.is_file():
            issues.append(Issue("error", "P043", "缺少 locale/%s.json" % lang, "locale/%s.json" % lang))
            continue
        try:
            data = json.loads(_read(path))
        except Exception as exc:  # noqa: BLE001
            issues.append(Issue("error", "P044", "locale/%s.json 非法：%s" % (lang, exc), "locale/%s.json" % lang))
            continue
        meta = data.get("meta") or {}
        if not str(meta.get("title", "")).strip() or not str(meta.get("description", "")).strip():
            issues.append(Issue("error", "P045", "locale/%s.json 缺 meta.title/meta.description" % lang, "locale/%s.json" % lang))


def _check_skill(root, issues):
    path = root / "skills" / SKILL_NAME / "SKILL.md"
    if not path.is_file():
        issues.append(Issue("error", "P050", "缺少 skills/%s/SKILL.md" % SKILL_NAME, "skills/%s/SKILL.md" % SKILL_NAME))
        return
    text = _read(path)
    data, body = parse_frontmatter(text)
    if not data:
        issues.append(Issue("error", "P051", "SKILL.md 缺少 YAML frontmatter", "SKILL.md"))
        return
    if data.get("name") != SKILL_NAME:
        issues.append(Issue("error", "P052", "skill name 必须是 %s" % SKILL_NAME, "SKILL.md"))
    if not str(data.get("description", "")).strip():
        issues.append(Issue("error", "P053", "skill description 不能为空", "SKILL.md"))
    extra = set(data) - SKILL_ALLOWED - {"__nested__"}
    if extra:
        issues.append(Issue("error", "P054", "frontmatter 含 DSH 不认识的字段：%s" % sorted(extra), "SKILL.md"))
    for legacy in ("disableModelInvocation", "modelInvocable", "userInvocable"):
        if legacy in data:
            issues.append(Issue("error", "P055", "使用了旧字段 %s" % legacy, "SKILL.md"))
    if SKILL_BACKTICK_ARTIFACT in text:
        issues.append(Issue("error", "P056", "正文含转义残留（反斜杠+反引号），会原样显示", "SKILL.md"))
    if len(text) > 8192:
        issues.append(Issue("error", "P057", "SKILL.md 超过 8192 字符（DSH 标准预设会裁剪）", "SKILL.md"))
    if len(body.strip()) < 1200:
        issues.append(Issue("warn", "P058", "SKILL.md 正文偏短"))
    for rel in REFERENCE_FILES:
        ref = root / "skills" / SKILL_NAME / "references" / rel
        if not ref.is_file():
            issues.append(Issue("error", "P059", "缺少 references/%s" % rel, "references/%s" % rel))
    for role in ("verifier.md", "reviewer.md"):
        if not (root / "prompts" / "roles" / role).is_file():
            issues.append(Issue("error", "P060", "缺少 prompts/roles/%s" % role, "prompts/roles/%s" % role))


def _check_versions(root, issues, versions):
    """Keep the package, engine, skill, and changelog versions in lockstep."""
    engine = root / "skills" / SKILL_NAME / "scripts" / "forgekit" / "__init__.py"
    if engine.is_file():
        match = re.search(r'__version__\s*=\s*"([^"]+)"', _read(engine))
        versions["forgekit"] = match.group(1) if match else ""
    skill = root / "skills" / SKILL_NAME / "SKILL.md"
    if skill.is_file():
        head = _read(skill).split("\n---", 1)[0]
        match = re.search(r'^\s+version:\s*"?([^"\n]+)"?', head, re.M)
        versions["skill"] = match.group(1).strip() if match else ""
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        match = re.search(r"^##\s*\[?v?(\d+\.\d+\.\d+)", _read(changelog), re.M)
        versions["CHANGELOG"] = match.group(1) if match else ""
    values = {k: v for k, v in versions.items() if v}
    distinct = sorted(set(values.values()))
    if len(distinct) > 1:
        issues.append(Issue("error", "P047", "版本号不一致：%s" % values, "package.json"))


def _check_legacy(root, issues):
    for rel in (".claude-plugin", ".zcode-plugin", "agents", "commands"):
        if (root / rel).exists():
            issues.append(Issue("error", "P070", "残留旧宿主结构 %s（DSH 不会加载，且会误导读者）" % rel, rel))
    for path in root.rglob("*"):
        if any(part in FORBIDDEN_CACHE for part in path.parts):
            issues.append(Issue("error", "P071", "存在缓存目录 %s" % path, str(path)))
            break


def _check_templates(root, issues):
    templates = root / "skills" / SKILL_NAME / "templates"
    if not templates.is_dir():
        issues.append(Issue("error", "P080", "缺少 templates/", "templates"))
        return
    for name in ("desktop-companion", "wheel-rover"):
        meta = templates / name / "blueprint.json"
        if not meta.is_file():
            issues.append(Issue("error", "P081", "缺少蓝本 %s" % name, "templates/%s" % name))
            continue
        try:
            data = json.loads(_read(meta))
        except Exception as exc:  # noqa: BLE001
            issues.append(Issue("error", "P082", "%s/blueprint.json 非法：%s" % (name, exc), "templates/%s/blueprint.json" % name))
            continue
        for key in ("name", "slug", "one_liner", "cost_cny", "time", "difficulty", "domains", "needs", "tags"):
            if key not in data:
                issues.append(Issue("error", "P083", "%s/blueprint.json 缺字段 %s" % (name, key), "templates/%s/blueprint.json" % name))
        if data.get("slug") != name:
            issues.append(Issue("error", "P084", "%s 的 slug 必须等于目录名" % name, "templates/%s/blueprint.json" % name))


def _check_docs(root, issues):
    readme = root / "README.md"
    if not readme.is_file():
        issues.append(Issue("error", "P090", "缺少 README.md", "README.md"))
    else:
        text = _read(readme)
        for needle in ("DeepSeek Harness", "rf_", "cordis.patch.yml"):
            if needle not in text:
                issues.append(Issue("warn", "P091", "README 没有提到 %s" % needle, "README.md"))
    for rel in (
        "docs/design.md",
        "docs/CONTRIBUTING.md",
        "docs/acceptance.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "tests/plugin.test.mjs",
    ):
        if not (root / rel).is_file():
            issues.append(Issue("error", "P092", "缺少 %s" % rel, rel))


def validate_plugin(root):
    root = Path(root).resolve()
    issues = []
    versions = {}
    _check_package(root, issues, versions)
    _check_patch(root, issues)
    _check_node_files(root, issues)
    _check_display(root, issues)
    _check_skill(root, issues)
    _check_versions(root, issues, versions)
    _check_legacy(root, issues)
    _check_templates(root, issues)
    _check_docs(root, issues)
    return issues, versions



def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(prog="validate_plugin.py", description="校验 DSH robot-forge bundle 的结构")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[4]))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    issues, versions = validate_plugin(root)
    errors = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warn"]
    if args.json:
        print(json.dumps({"root": str(root), "versions": versions, "issues": [i.as_dict() for i in issues]}, ensure_ascii=False, indent=2))
    else:
        print("robot-forge DSH bundle 校验：%s" % root)
        for issue in issues:
            print("  " + str(issue))
        print("")
        print("%d 错误 · %d 警告" % (len(errors), len(warnings)))
        if not errors:
            print("结构与跨文件一致性都过了。")
    return 1 if errors else 0
