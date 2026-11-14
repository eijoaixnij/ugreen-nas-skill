# 绿联NAS (UGREEN NAS) Skill

[![CI](https://github.com/eijoaixnij/ugreen-nas-skill/actions/workflows/ci.yml/badge.svg)](https://github.com/eijoaixnij/ugreen-nas-skill/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

绿联NAS (UGREEN NAS / UGOS Pro) 管理助手 Skill，通过私有 HTTP API 实现系统监控与文件管理操作。

> ⚠️ **注意**：此 API 为绿联非公开私有 API，基于逆向工程和社区 SDK 整理，非绿联官方文档。固件升级后接口可能发生变化。

## 功能

### 系统监控

- 系统信息（型号、序列号、硬件配置、系统版本）
- CPU / 内存使用率、上传 / 下载速度
- CPU 温度、硬盘温度、风扇转速
- 存储空间、系统状态、网络连接信息

### 文件管理

- 目录列表、创建文件夹
- 复制 / 移动（支持 skip / overwrite / keep-both 冲突策略）
- 重命名、删除（回收站 / 永久删除）
- 文件上传、下载、权限检测

## 安装到 Trae

有三种方式，任选其一。

### 方式一：克隆到项目级 skills 目录（推荐）

在需要使用的项目根目录下执行：

```bash
git clone https://github.com/eijoaixnij/ugreen-nas-skill.git /tmp/ugreen-nas-skill
mkdir -p .trae/skills
cp -r /tmp/ugreen-nas-skill/skills/ugreen-nas .trae/skills/
pip install -r /tmp/ugreen-nas-skill/requirements.txt
```

目录结构应变为：

```
your-project/
└── .trae/
    └── skills/
        └── ugreen-nas/
            ├── SKILL.md
            ├── references/
            └── scripts/ugreen_nas_client.py
```

### 方式二：安装到用户级 skills 目录（全局可用）

```bash
mkdir -p ~/.trae/skills
cp -r /tmp/ugreen-nas-skill/skills/ugreen-nas ~/.trae/skills/
```

安装到用户级后，所有项目中的对话都能触发该 skill。

### 方式三：作为插件安装

本仓库同时是一个完整的 Trae 插件（含 `.trae-plugin/plugin.json`）。将整个仓库放入本地插件目录即可：

```bash
cp -r /tmp/ugreen-nas-skill ~/.trae/plugins/ugreen-nas/0.1.0
```

重启 Trae 后插件生效，插件名称为「绿联NAS助手」。

### 验证安装

打开 Trae 对话，输入例如：

> 帮我看看绿联NAS现在的运行状态，地址 http://192.168.1.100:9999，用户名 admin，密码 ******

若 skill 正常加载，Agent 会自动读取 `SKILL.md` 并按认证流程调用 `/ugreen/v1/verify/check` 等接口。

### 卸载

```bash
rm -rf .trae/skills/ugreen-nas        # 项目级
rm -rf ~/.trae/skills/ugreen-nas      # 用户级
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 使用 Python 客户端

```bash
# 查看 NAS 状态
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py \
  --url http://192.168.1.100:9999 \
  --user admin \
  --password your-password \
  --status

# 列出目录
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py \
  --url http://192.168.1.100:9999 \
  --user admin \
  --password your-password \
  --list /Documents

# 上传文件
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py \
  --url http://192.168.1.100:9999 \
  --user admin \
  --password your-password \
  --upload /local/file.txt /Documents

# 下载文件
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py \
  --url http://192.168.1.100:9999 \
  --user admin \
  --password your-password \
  --download /Documents/report.pdf /local/report.pdf
```

### 作为模块使用

```python
from ugreen_nas_client import UgreenNASClient

nas = UgreenNASClient("http://192.168.1.100:9999", "admin", "your-password")
nas.login()

# 查看状态
info = nas.sys_info()
dev = nas.device_monitoring()
print(f"CPU: {dev['cpu_usage_rate']}%  内存: {dev['ram_usage_rate']}%")

# 列出文件
files = nas.list_dir("/Documents")
for f in files:
    print(f["name"])
```

## 认证机制

1. 调用 `/ugreen/v1/verify/check` 获取 RSA 公钥（响应头 `x-rsa-token`）
2. 使用 RSA PKCS#1 v1.5 加密密码
3. 调用 `/ugreen/v1/verify/login` 登录，获取 `token_id`、`token`、`public_key`、`uid`
4. 后续请求携带认证头：
   - `x-ugreen-security-key`: token_id
   - `x-ugreen-token`: RSA 加密后的 token

两种认证风格：

- **系统监控接口**：使用 `?token=<token原文>` 查询参数
- **文件管理接口**：使用 `x-ugreen-token: <RSA加密token>` 请求头

## 项目结构

```
.
├── .github/
│   ├── scripts/
│   │   └── validate_skill.py         # 结构与 manifest 校验脚本
│   └── workflows/
│       └── ci.yml                    # GitHub Actions 语法检查
├── .trae-plugin/
│   └── plugin.json                   # 插件元数据
├── assets/
│   └── icon.svg                      # 插件图标
├── skills/
│   └── ugreen-nas/
│       ├── SKILL.md                  # Skill 主文档
│       ├── references/
│       │   ├── api-reference.md      # 完整 API 参考
│       │   └── examples.md           # 代码示例
│       └── scripts/
│           └── ugreen_nas_client.py  # Python 客户端
├── requirements.txt
├── LICENSE
├── .gitignore
└── README.md
```

## 开发与校验

提交前可在本地跑一遍与 CI 相同的检查：

```bash
pip install -r requirements.txt
python .github/scripts/validate_skill.py
python -m compileall -q skills/ugreen-nas/scripts .github/scripts
python skills/ugreen-nas/scripts/ugreen_nas_client.py --help
```

CI（[ci.yml](.github/workflows/ci.yml)）会在 push 到 `main` 和提交 PR 时自动执行：

1. 校验 `plugin.json` 可解析且含必填字段
2. 校验 `SKILL.md` frontmatter 的 `name` / `description`，并检查文档引用的本地文件是否存在
3. 校验 workflow YAML 语法
4. Python 语法编译检查
5. CLI 冒烟测试（`--help` 可正常输出）

## 免责声明

本项目为非官方社区项目，与绿联（UGREEN）无关联。使用本项目造成的任何数据丢失或设备故障，由使用者自行承担责任。

## 许可证

[MIT License](LICENSE) © 2026 eijoaixnij
