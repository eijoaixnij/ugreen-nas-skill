# 绿联NAS (UGREEN NAS) Skill

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
├── .trae-plugin/
│   └── plugin.json              # 插件元数据
├── assets/
│   └── icon.svg                 # 插件图标
├── skills/
│   └── ugreen-nas/
│       ├── SKILL.md             # Skill 主文档
│       ├── references/
│       │   ├── api-reference.md # 完整 API 参考
│       │   └── examples.md      # 代码示例
│       └── scripts/
│           └── ugreen_nas_client.py  # Python 客户端
├── requirements.txt
├── .gitignore
└── README.md
```

## 免责声明

本项目为非官方社区项目，与绿联（UGREEN）无关联。使用本项目造成的任何数据丢失或设备故障，由使用者自行承担责任。
