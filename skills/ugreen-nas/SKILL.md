---
name: ugreen-nas
description: "绿联NAS (UGREEN NAS / UGOS Pro) 管理助手。通过私有HTTP API实现登录认证、系统监控（CPU/内存/温度/存储/网络/系统状态）、文件管理（目录列表/创建文件夹/复制/移动/重命名/上传/下载/删除/回收站）等操作。当用户提到绿联、UGREEN、UGOS、NASync、NAS私有云、DXP系列、DH系列，或要求查看NAS状态、管理NAS文件、上传下载NAS文件、查询CPU温度/存储空间时触发。"
---

# 绿联NAS (UGREEN NAS / UGOS Pro) 管理助手

通过绿联NAS的私有HTTP API（UGOS Pro系统），实现系统监控与文件管理操作。**注意：此API为非公开私有API，基于逆向工程和社区SDK整理，非绿联官方文档。**

## 定位与边界

**做**：登录认证、系统信息查询、硬件监控、文件浏览/上传/下载/复制/移动/重命名/删除/回收站

**不做**：Docker容器管理、下载任务(BT/PT)管理、应用中心管理、用户权限管理（这些模块的API端点未完整逆向，如需操作请通过Web UI）

---

## 前置条件

使用前需要用户提供以下信息：

| 参数 | 说明 | 示例 |
|------|------|------|
| `NAS_URL` | NAS的访问地址，含协议和端口 | `http://192.168.1.100:9999` 或 `https://nas.example.com` |
| `USERNAME` | 登录用户名 | `admin` |
| `PASSWORD` | 登录密码 | `your-password` |

**连接方式**：

- **局域网直连**：使用NAS的局域网IP + 端口（默认HTTP 9999，HTTPS 9443）
- **UGREENlink远程访问**：通过UGREENlink ID解析地址（`https://{alias}.{relayDomain}`）

**安全说明**：

- 密码使用RSA公钥加密后传输（PKCS#1 v1.5 padding），不会明文发送
- 登录后获取的token也会用服务器公钥加密后放在请求头中
- 如果NAS开启了2FA，登录需要额外的验证码步骤

---

## 认证流程（核心，所有操作前必须完成）

### 步骤1：获取RSA公钥

```
POST /ugreen/v1/verify/check
Content-Type: application/json

{"username": "admin"}
```

响应头 `x-rsa-token` 包含RSA公钥（Base64编码的PEM格式）。

### 步骤2：RSA加密密码

用步骤1获取的公钥，对密码做 RSA/PKCS#1 v1.5 加密，再Base64编码。

Python实现（需 `pycryptodome`）：

```python
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
import base64

def rsa_encrypt_base64(plaintext: str, public_key_pem: str) -> str:
    key = RSA.import_key(public_key_pem)
    cipher = PKCS1_v1_5.new(key)
    encrypted = cipher.encrypt(plaintext.encode())
    return base64.b64encode(encrypted).decode()
```

### 步骤3：登录

```
POST /ugreen/v1/verify/login
Content-Type: application/json

{
  "username": "admin",
  "password": "<RSA加密后的密码Base64>",
  "otp": true,
  "keepalive": true,
  "is_simple": true
}
```

成功响应（`code: 200`）的 `data` 字段包含：

```json
{
  "token_id": "...",
  "token": "...",
  "uid": 1000,
  "public_key": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n"
}
```

**OTP场景**：如果NAS开启了双重验证，响应 `code` 不是200，`data` 会返回 `token_id`，需要调用 `/ugreen/v1/verify/code/login` 提交验证码。

### 步骤4：后续请求的认证头

所有需要认证的请求，必须携带以下两个请求头：

```
x-ugreen-security-key: <token_id>
x-ugreen-token: <RSA加密后的token，使用data中的public_key>
```

其中 `x-ugreen-token` 的值 = `rsa_encrypt_base64(token, public_key)`。

### 步骤5：验证登录状态

```
GET /ugreen/v1/verify/is_login
Headers: x-ugreen-security-key, x-ugreen-token
```

响应 `code: 200` 表示token有效。

---

## 能力模块

### 模块A：系统监控

所有监控接口为 `GET` 请求，使用 `?token=<token原文>` 方式认证。

| 功能 | 端点 | 说明 |
|------|------|------|
| 系统信息 | `GET /ugreen/v1/sysinfo/machine/common?token=X` | NAS名称、型号、序列号、MAC、系统版本、运行时长、CPU/内存/网络硬件信息 |
| 系统状态 | `GET /ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus&token=X` | 设备名、上次启动时间、运行状态消息 |
| 设备监控 | `GET /ugreen/v1/desktop/components/data?id=desktop.component.DeviceMonitoring&token=X` | CPU使用率、内存使用率、上传/下载速度 |
| 温度监控 | `GET /ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring&token=X` | CPU温度、硬盘温度列表、风扇转速、散热状态 |
| 存储空间 | `GET /ugreen/v1/desktop/components/data?id=desktop.component.StorageSpace&token=X` | 存储池/卷信息 |
| 网络连接 | `GET /ugreen/v1/user/priority_link?token=X` | 主机IP、IPv4/IPv6列表、HTTP/HTTPS端口、UGREENlink信息 |

> **注意**：这些接口使用 `?token=` 查询参数认证，token为登录返回的原始token字符串（不需要RSA加密）。

### 模块B：文件管理

文件管理接口使用 `x-ugreen-security-key` + `x-ugreen-token` 认证头。

| 功能 | 方法 | 端点 |
|------|------|------|
| 列出目录 | POST | `/ugreen/v2/filemgr/getDirFileListV2` |
| 创建文件夹 | POST | `/ugreen/v2/filemgr/createFolder` |
| 复制/移动 | POST | `/ugreen/v2/filemgr/cpOrMvPath` |
| 重命名 | POST | `/ugreen/v2/filemgr/rename` |
| 删除/回收站 | POST | `/ugreen/v2/filemgr/delPaths` |
| 下载token | GET | `/ugreen/v2/filemgr/getDownloadToken?paths=...&intranet_share_id=0&coding=true` |
| 权限检测 | POST | `/ugreen/v1/filemgr/detectionPermissions` |
| 上传(预检查) | POST | `/ugreen/v1/filemgr/fileUpload` |
| 上传(内容) | POST | `/ugreen/v1/filemgr/fileUploadV2` |

详细的请求体和响应格式见 `references/api-reference.md`。

---

## 工作流指引

### 场景1：查看NAS运行状态

1. 确认用户提供了 NAS_URL、USERNAME、PASSWORD
2. 执行认证流程获取 token
3. 依次请求以下接口获取完整状态：
   - `sysinfo/machine/common` → 硬件基本信息
   - `desktop.component.DeviceMonitoring` → CPU/内存/网速
   - `desktop.component.TemperatureMonitoring` → 温度/风扇
   - `desktop.component.StorageSpace` → 存储
4. 汇总为可读的状态报告

### 场景2：浏览/管理文件

1. 认证获取 token 与 public_key
2. 调用 `getDirFileListV2` 列出目录内容
3. 根据用户意图调用对应的文件操作接口
4. **删除操作前必须二次确认**：`delPaths` 的 `forever=true` 会永久删除，`forever=false` 放入回收站

### 场景3：上传文件到NAS

1. 认证
2. 构造上传UUID：`{random_uuid}_1_{md5(file_content)}`
3. 调用 `fileUpload` 做预上传（FormData，含 uuid、dir、filename、size、action_type 等）
4. 调用 `getUpdateTmpInfo` 获取临时上传信息
5. 调用 `fileUploadV2` 上传实际文件内容（请求头 `ug-param` 为JSON参数，body为文件二进制）

### 场景4：从NAS下载文件

1. 认证
2. 先调用 `detectionPermissions` 检测权限
3. 调用 `getDownloadToken` 获取下载链接 `dl_url`
4. GET `${NAS_URL}${dl_url}` 下载文件（带认证头）

---

## 核心约束

1. **认证优先**：任何API调用前必须先完成登录，获取有效的 token 和 public_key
2. **删除需确认**：永久删除文件（`forever=true`）前必须明确告知用户并获得确认
3. **不硬编码密码**：密码仅用于RSA加密后发送，不写入文件、不记录日志
4. **RSA加密正确**：必须使用 PKCS#1 v1.5 padding，不是 OAEP
5. **Token加密**：`x-ugreen-token` 头的值是用服务器返回的 public_key 对 token 做RSA加密后的Base64，不是token原文
6. **两种认证风格**：系统监控接口用 `?token=原文`；文件管理接口用 `x-ugreen-token: 加密后token`

---

## 环境与依赖

推荐使用 Python + `requests` + `pycryptodome`：

```bash
python3 -c "import requests, Crypto" 2>/dev/null || pip3 install requests pycryptodome
```

详细资源：

- `references/api-reference.md` — 所有端点的请求/响应详细说明
- `references/examples.md` — Python/curl 完整代码示例
- `scripts/ugreen_nas_client.py` — 可直接运行的Python客户端

**快速调用脚本示例**：

```bash
# 查看NAS状态
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py --url http://192.168.1.100:9999 --user admin --password your-pwd --status

# 列出目录
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py --url http://192.168.1.100:9999 --user admin --password your-pwd --list /Documents

# 上传文件
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py --url http://192.168.1.100:9999 --user admin --password your-pwd --upload /local/file.txt /Documents

# 下载文件
python3 skills/ugreen-nas/scripts/ugreen_nas_client.py --url http://192.168.1.100:9999 --user admin --password your-pwd --download /Documents/report.pdf /local/report.pdf
```
