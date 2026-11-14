# 绿联NAS API 详细参考

本文档列出绿联NAS (UGOS Pro) 私有API的所有已知端点、请求参数和响应格式。

## 通用约定

### Base URL

`{NAS_URL}` = 协议://IP:端口，例如 `http://192.168.1.100:9999`

### 响应格式

所有接口返回JSON：

```json
{
  "code": 200,
  "msg": "success",
  "data": { },
  "time": 0.001
}
```

常见错误码：

- `200`: 成功
- `1003`: 账号或密码错误
- `1024`: 授权超时，请重新登录
- `1301`: 路径不存在

### 两种认证风格

**风格1（桌面组件/系统信息）**：查询参数 `?token=<token原文>`

- 适用于 `/ugreen/v1/sysinfo/*` 和 `/ugreen/v1/desktop/components/*`

**风格2（文件管理）**：请求头

```
x-ugreen-security-key: <token_id>
x-ugreen-token: <RSA加密token后的Base64>
```

- 适用于 `/ugreen/v2/filemgr/*` 和 `/ugreen/v1/filemgr/*`

---

## 认证相关

### 1. 获取RSA公钥

```
POST /ugreen/v1/verify/check
Content-Type: application/json

{"username": "admin"}
```

- **响应头**: `x-rsa-token: <Base64编码的PEM公钥>`
- **响应体**: `{"code":200,"msg":"success","data":null}`

### 2. 登录

```
POST /ugreen/v1/verify/login
Content-Type: application/json

{
  "username": "admin",
  "password": "<RSA PKCS1_v1.5加密后的密码Base64>",
  "otp": true,
  "keepalive": true,
  "is_simple": true
}
```

**成功响应** (`code: 200`):

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "token_id": "abc123...",
    "token": "def456...",
    "uid": 1000,
    "public_key": "-----BEGIN PUBLIC KEY-----\nMIIBIjAN...\n-----END PUBLIC KEY-----\n"
  }
}
```

**OTP响应** (开启2FA时):

```json
{
  "code": 512,
  "msg": "need otp",
  "data": {
    "token_id": "...",
    "uid": 1000,
    "role": 1,
    "urgent_email": "user@example.com"
  }
}
```

### 3. OTP验证码登录

```
POST /ugreen/v1/verify/code/login
Content-Type: application/json

{
  "code": "123456",
  "type": 1,
  "token_id": "<登录返回的token_id>",
  "trust_info": {
    "client_type": "sdk",
    "system": "node",
    "dev_name": "ugreen-nas-skill"
  },
  "trust": true
}
```

### 4. 检查登录状态

```
GET /ugreen/v1/verify/is_login
Headers: x-ugreen-security-key, x-ugreen-token
```

---

## 系统监控（风格1认证）

### 系统信息

```
GET /ugreen/v1/sysinfo/machine/common?token=<token>
```

**响应示例**:

```json
{
  "common": {
    "nas_name": "DXP4800PLUS",
    "uglink_id": "",
    "nas_owner": "owner@example.com",
    "model": "DXP4800 Plus",
    "serial": "SNXXXXXXXX",
    "mac": ["AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:00"],
    "system_version": "1.19.0.0000",
    "run_time": 200635,
    "last_turn_on_time": "2024-07-08 14:45:43"
  },
  "hardware": {
    "cpu": [{"model": "Intel(R) Pentium(R) Gold 8505", "ghz": 4400, "core": 5, "thread": 6, "temperature": 42}],
    "mem": [{"model": "M425R1GB4BB0-CQKOL", "size": 8589934592, "mhz": "4800 MHz"}],
    "net": [{"model": "eth0", "ip": "192.168.1.100", "mac": "..."}, {"model": "eth1", "ip": "-", "mac": "..."}],
    "ups": null,
    "usb": null
  }
}
```

### 系统状态

```
GET /ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus&token=<token>
```

**响应**:

```json
{
  "dev_name": "DXP4800PLUS",
  "last_boot_date": "07-08 14:45",
  "last_boot_time": 1720439143,
  "message": "The system is running normally.",
  "status": 0,
  "total_run_time": 200835,
  "type": 2
}
```

### 设备监控（CPU/内存/网速）

```
GET /ugreen/v1/desktop/components/data?id=desktop.component.DeviceMonitoring&token=<token>
```

**响应**:

```json
{
  "cpu_usage_rate": 0.67,
  "ram_usage_rate": "13.09",
  "upload_speed": {"unit": "KB/s", "value": 0.06},
  "download_speed": {"unit": "KB/s", "value": 2.4},
  "type": 3
}
```

### 温度监控

```
GET /ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring&token=<token>
```

**响应**:

```json
{
  "cpu_status": 0,
  "cpu_temperature": 43,
  "disk_list": [{"name": "sda", "temperature": 38}, {"name": "sdb", "temperature": 36}],
  "fan_speed": 590,
  "fan_status": 0,
  "message": "The temperature is normal, and the heat dissipation is good.",
  "status": 0,
  "type": 6
}
```

### 存储空间

```
GET /ugreen/v1/desktop/components/data?id=desktop.component.StorageSpace&token=<token>
```

### 网络连接信息

```
GET /ugreen/v1/user/priority_link?token=<token>
```

**响应**:

```json
{
  "ddns": [],
  "host": "192.168.1.100",
  "uglink": "",
  "uglink_id": "",
  "ipv_4": ["192.168.1.100"],
  "ipv_6": [],
  "http_port": 9999,
  "https_port": 9443
}
```

---

## 文件管理（风格2认证）

### 列出目录

```
POST /ugreen/v2/filemgr/getDirFileListV2
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token
Referer: {NAS_URL}/filemgr/?_filemgr=a58981e8

{
  "path": "/Documents",
  "limit": 2000,
  "page": 1,
  "is_shield_recycle": false,
  "data_type": 0,
  "left_no_page_show": false,
  "left_count": 5000,
  "sort_type": 1,
  "reverse": false,
  "permission": 4,
  "root_type": 3
}
```

**参数说明**:

- `path`: 目录路径，根目录用空字符串 `""`
- `root_type`: 3=共享目录, 4=个人目录
- `sort_type`: 排序类型
- `data_type`: 0=全部

**响应** (`data.right_files.files` 为文件列表):

```json
{
  "code": 200,
  "data": {
    "right_files": {
      "files": [
        {
          "name": "report.pdf",
          "path": "/Documents/report.pdf",
          "size": 1048576,
          "type": "file",
          "mtime": 1720000000,
          "suffix": "pdf"
        }
      ]
    }
  }
}
```

### 创建文件夹

```
POST /ugreen/v2/filemgr/createFolder
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token

{"path": "/Documents/Projects", "no_recursive_creation": false}
```

- `no_recursive_creation`: `false` 表示递归创建（mkdir -p），`true` 表示仅创建最后一级

### 复制/移动

```
POST /ugreen/v2/filemgr/cpOrMvPath
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token

{
  "src": ["/Downloads/a.txt", "/Downloads/b.txt"],
  "dst": "/Documents/",
  "action_type": 1,
  "type": false,
  "intranet_share_id": 0
}
```

- `src`: 源路径数组
- `dst`: 目标目录
- `action_type`: 冲突处理 — `0`=skip跳过, `1`=overwrite覆盖, `3`=keep-both保留两者
- `type`: `false`=复制, `true`=移动

### 重命名

```
POST /ugreen/v2/filemgr/rename
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token

{"path": "/Documents/old.txt", "new_name": "new.txt"}
```

### 删除

```
POST /ugreen/v2/filemgr/delPaths
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token

{"paths": ["/Documents/old.txt"], "forever": false}
```

- `forever`: `false`=放入回收站, `true`=永久删除

### 权限检测（下载前调用）

```
POST /ugreen/v1/filemgr/detectionPermissions
Content-Type: application/json
Headers: x-ugreen-security-key, x-ugreen-token

{"paths": ["/Documents/report.pdf"], "type": 4, "intranet_share_id": 0}
```

### 获取下载token

```
GET /ugreen/v2/filemgr/getDownloadToken?paths=/Documents/report.pdf&intranet_share_id=0&coding=true
Headers: x-ugreen-security-key, x-ugreen-token
```

**响应**:

```json
{
  "code": 200,
  "data": {
    "dl_url": "/ugreen/v1/filemgr/download?token=xxx&..."
  }
}
```

然后 GET `{NAS_URL}{dl_url}` 下载文件。

### 上传文件

上传分三步：

**步骤1：预上传**

```
POST /ugreen/v1/filemgr/fileUpload
Headers: x-ugreen-security-key, x-ugreen-token
Content-Type: multipart/form-data

uuid: {random_uuid}_1_{md5(file)}
dir: /Documents
action_type: 0
size: <文件大小字节>
begin_size: 0
current_size: 0
change_time: <时间戳>
filename: hello.txt
resume: true
first_request: true
file: <空Blob占位>
```

- `action_type`: 0=skip, 1=overwrite, 3=keep-both

**步骤2：获取临时上传信息**

```
GET /ugreen/v1/filemgr/getUpdateTmpInfo?dir=/Documents&uuid={uuid}&filename=hello.txt&action_type=0&size={size}
Headers: x-ugreen-security-key, x-ugreen-token
```

**步骤3：上传文件内容**

```
POST /ugreen/v1/filemgr/fileUploadV2?
Headers:
  x-ugreen-security-key: <token_id>
  x-ugreen-token: <encrypted_token>
  ug-param: {"uuid":"...","file_name":"hello.txt","action_type":0,"size":123,"current_size":123,"resume":true,"dir":"/Documents","change_time":1234567890,"is_live_photo":false,"first_request":false,"begin_size":0}

Body: <文件二进制内容>
```

---

## UGREENlink 地址解析

如果只有UGREENlink ID（别名），需要先解析为实际访问地址：

```
POST https://api.ugnas.com/api/p2p/v2/ta/nodeInfo/byAlias
Content-Type: application/json

{"alias": "your-ugreenlink-alias"}
```

**响应**:

```json
{
  "code": 200,
  "data": {
    "relayDomain": "eur6.ug.link"
  }
}
```

实际访问地址 = `https://{alias}.{relayDomain}`
