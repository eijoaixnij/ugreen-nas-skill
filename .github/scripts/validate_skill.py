#!/usr/bin/env python3
"""校验 skill 项目结构、manifest 与 SKILL.md frontmatter。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
errors = []


def fail(msg: str) -> None:
    errors.append(msg)


# 1. plugin.json 可解析且必填字段存在
manifest_path = ROOT / ".trae-plugin" / "plugin.json"
if not manifest_path.is_file():
    fail(".trae-plugin/plugin.json 不存在")
else:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("name", "version", "description", "skills"):
            if not manifest.get(key):
                fail(f"plugin.json 缺少字段: {key}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", ""))):
            fail(f"plugin.json 的 version 不是 semver: {manifest.get('version')!r}")
    except json.JSONDecodeError as exc:
        fail(f"plugin.json JSON 解析失败: {exc}")

# 2. 每个 skill 目录必须有 SKILL.md，且 frontmatter 含 name/description
skills_dir = ROOT / "skills"
skill_dirs = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
if not skill_dirs:
    fail("skills/ 下未找到任何 skill 目录")

for skill_dir in skill_dirs:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(f"{skill_dir.name}: 缺少 SKILL.md")
        continue
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        fail(f"{skill_dir.name}/SKILL.md 缺少 frontmatter")
        continue
    parts = text.split("---", 2)
    if len(parts) < 3:
        fail(f"{skill_dir.name}/SKILL.md frontmatter 未闭合")
        continue
    front = parts[1]
    name_match = re.search(r"^name:\s*(\S+)", front, re.MULTILINE)
    desc_match = re.search(r"^description:\s*(.+)$", front, re.MULTILINE)
    if not name_match:
        fail(f"{skill_dir.name}/SKILL.md frontmatter 缺少 name")
    elif name_match.group(1) != skill_dir.name:
        fail(f"{skill_dir.name}: frontmatter name={name_match.group(1)!r} 与目录名不一致")
    if not desc_match or len(desc_match.group(1).strip()) < 20:
        fail(f"{skill_dir.name}/SKILL.md 的 description 缺失或过短")

    # 3. 文档中引用的本地文件必须存在
    for ref in re.findall(r"`((?:references|scripts)/[\w./-]+)`", text):
        if not (skill_dir / ref).exists():
            fail(f"{skill_dir.name}/SKILL.md 引用了不存在的文件: {ref}")

# 4. 仓库元数据
for required in ("README.md", "LICENSE", "requirements.txt"):
    if not (ROOT / required).is_file():
        fail(f"缺少 {required}")

if errors:
    print("校验失败:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)

print(f"校验通过: {len(skill_dirs)} 个 skill，结构完整。")
