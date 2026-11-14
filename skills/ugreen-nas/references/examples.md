# 绿联NAS API 代码示例

## Python 完整封装（推荐）

### 依赖安装

```bash
pip install requests pycryptodome
```

### 完整客户端代码

```python
import base64
import hashlib
import json
import os
import time
import uuid
from typing import Optional

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA


class UgreenNASClient:
    """绿联NAS (UGOS Pro) API 客户端"""

    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = False):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session: Optional[dict] = None

        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ---------- 认证 ----------

    @staticmethod
    def _rsa_encrypt_base64(plaintext: str, public_key_pem: str) -> str:
        """使用 RSA PKCS#1 v1.5 加密并返回 Base64"""
        key = RSA.import_key(public_key_pem)
        cipher = PKCS1_v1_5.new(key)
        encrypted = cipher.encrypt(plaintext.encode())
        return base64.b64encode(encrypted).decode()

    def _get_rsa_public_key(self) -> str:
        """获取RSA公钥（从响应头 x-rsa-token）"""
        url = f"{self.base_url}/ugreen/v1/verify/check"
        resp = requests.post(url, json={"username": self.username}, verify=self.verify_ssl)
        rsa_token = resp.headers.get("x-rsa-token")
        if not rsa_token:
            raise RuntimeError("响应头中未找到 x-rsa-token")
        return rsa_token

    def login(self) -> dict:
        """登录，返回 session 字典"""
        rsa_pubkey = self._get_rsa_public_key()
        encrypted_password = self._rsa_encrypt_base64(self.password, rsa_pubkey)

        url = f"{self.base_url}/ugreen/v1/verify/login"
        payload = {
            "username": self.username,
            "password": encrypted_password,
            "otp": True,
            "keepalive": True,
            "is_simple": True,
        }
        resp = requests.post(url, json=payload, verify=self.verify_ssl)
        data = resp.json()

        if data["code"] != 200:
            if "token_id" in (data.get("data") or {}):
                raise RuntimeError(
                    f"需要OTP验证，请调用 code_login。token_id={data['data']['token_id']}"
                )
            raise RuntimeError(f"登录失败: {data.get('msg')} (code={data['code']})")

        self.session = {
            "token_id": data["data"]["token_id"],
            "token": data["data"]["token"],
            "uid": data["data"]["uid"],
            "public_key": data["data"]["public_key"],
        }
        return self.session

    def code_login(self, token_id: str, code: str, trust: bool = True) -> dict:
        """OTP验证码登录"""
        url = f"{self.base_url}/ugreen/v1/verify/code/login"
        payload = {
            "code": code,
            "type": 1,
            "token_id": token_id,
            "trust_info": {"client_type": "sdk", "system": "python", "dev_name": "ugreen-nas-skill"},
            "trust": trust,
        }
        resp = requests.post(url, json=payload, verify=self.verify_ssl)
        data = resp.json()
        if data["code"] != 200:
            raise RuntimeError(f"OTP验证失败: {data.get('msg')}")
        self.session = {
            "token_id": data["data"]["token_id"],
            "token": data["data"]["token"],
            "uid": data["data"]["uid"],
            "public_key": data["data"]["public_key"],
        }
        return self.session

    def _auth_headers(self) -> dict:
        """生成文件管理接口所需的认证头"""
        if not self.session:
            raise RuntimeError("未登录，请先调用 login()")
        encrypted_token = self._rsa_encrypt_base64(self.session["token"], self.session["public_key"])
        return {
            "x-ugreen-security-key": self.session["token_id"],
            "x-ugreen-token": encrypted_token,
        }

    def check_login(self) -> bool:
        url = f"{self.base_url}/ugreen/v1/verify/is_login"
        resp = requests.get(url, headers=self._auth_headers(), verify=self.verify_ssl)
        return resp.json().get("code") == 200

    # ---------- 系统监控（风格1：?token= 原文） ----------

    def sys_info(self) -> dict:
        url = f"{self.base_url}/ugreen/v1/sysinfo/machine/common?token={self.session['token']}"
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    def device_monitoring(self) -> dict:
        url = (f"{self.base_url}/ugreen/v1/desktop/components/data"
               f"?id=desktop.component.DeviceMonitoring&token={self.session['token']}")
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    def temperature_monitoring(self) -> dict:
        url = (f"{self.base_url}/ugreen/v1/desktop/components/data"
               f"?id=desktop.component.TemperatureMonitoring&token={self.session['token']}")
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    def storage_space(self) -> dict:
        url = (f"{self.base_url}/ugreen/v1/desktop/components/data"
               f"?id=desktop.component.StorageSpace&token={self.session['token']}")
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    def system_status(self) -> dict:
        url = (f"{self.base_url}/ugreen/v1/desktop/components/data"
               f"?id=desktop.component.SystemStatus&token={self.session['token']}")
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    def priority_link(self) -> dict:
        url = f"{self.base_url}/ugreen/v1/user/priority_link?token={self.session['token']}"
        return requests.get(url, verify=self.verify_ssl).json()["data"]

    # ---------- 文件管理（风格2：认证头） ----------

    def list_dir(self, path: str = "", root_type: int = 3) -> list:
        """列出目录内容。root_type: 3=共享, 4=个人"""
        url = f"{self.base_url}/ugreen/v2/filemgr/getDirFileListV2"
        payload = {
            "path": path,
            "limit": 2000,
            "page": 1,
            "is_shield_recycle": False,
            "data_type": 0,
            "left_no_page_show": False,
            "left_count": 5000,
            "sort_type": 1,
            "reverse": False,
            "permission": 4,
            "root_type": root_type,
        }
        headers = {
            **self._auth_headers(),
            "Content-Type": "application/json",
            "Referer": f"{self.base_url}/filemgr/?_filemgr=a58981e8",
        }
        resp = requests.post(url, json=payload, headers=headers, verify=self.verify_ssl)
        return resp.json()["data"].get("right_files", {}).get("files", [])

    def mkdir(self, path: str, recursive: bool = True):
        url = f"{self.base_url}/ugreen/v2/filemgr/createFolder"
        payload = {"path": path, "no_recursive_creation": not recursive}
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()

    def copy(self, src, dst: str, action: str = "skip"):
        self._copy_or_move(src, dst, move=False, action=action)

    def move(self, src, dst: str, action: str = "skip"):
        self._copy_or_move(src, dst, move=True, action=action)

    def _copy_or_move(self, src, dst: str, move: bool, action: str):
        action_map = {"skip": 0, "overwrite": 1, "keep-both": 3}
        url = f"{self.base_url}/ugreen/v2/filemgr/cpOrMvPath"
        payload = {
            "src": src if isinstance(src, list) else [src],
            "dst": dst,
            "action_type": action_map[action],
            "type": move,
            "intranet_share_id": 0,
        }
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()

    def rename(self, path: str, new_name: str):
        url = f"{self.base_url}/ugreen/v2/filemgr/rename"
        payload = {"path": path, "new_name": new_name}
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()

    def delete(self, paths, forever: bool = False):
        url = f"{self.base_url}/ugreen/v2/filemgr/delPaths"
        payload = {"paths": paths if isinstance(paths, list) else [paths], "forever": forever}
        headers = {**self._auth_headers(), "Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()

    def download(self, remote_path: str, local_path: str):
        perm_url = f"{self.base_url}/ugreen/v1/filemgr/detectionPermissions"
        perm_payload = {"paths": [remote_path], "type": 4, "intranet_share_id": 0}
        requests.post(
            perm_url,
            json=perm_payload,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            verify=self.verify_ssl,
        )

        token_url = f"{self.base_url}/ugreen/v2/filemgr/getDownloadToken"
        params = {"paths": remote_path, "intranet_share_id": "0", "coding": "true"}
        token_resp = requests.get(
            token_url, params=params, headers=self._auth_headers(), verify=self.verify_ssl
        )
        dl_url = token_resp.json()["data"]["dl_url"]

        full_url = f"{self.base_url}{dl_url}"
        with requests.get(full_url, headers=self._auth_headers(), verify=self.verify_ssl, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def upload(self, local_path: str, remote_dir: str, remote_name: Optional[str] = None):
        if remote_name is None:
            remote_name = os.path.basename(local_path)

        with open(local_path, "rb") as f:
            file_content = f.read()

        file_size = len(file_content)
        file_md5 = hashlib.md5(file_content).hexdigest()
        upload_uuid = f"{uuid.uuid4()}_1_{file_md5}"

        pre_url = f"{self.base_url}/ugreen/v1/filemgr/fileUpload"
        form_data = {
            "uuid": upload_uuid,
            "dir": remote_dir,
            "action_type": "0",
            "size": str(file_size),
            "begin_size": "0",
            "current_size": "0",
            "change_time": str(int(time.time() * 1000)),
            "filename": remote_name,
            "resume": "true",
            "first_request": "true",
        }
        files = {"file": (remote_name, b"", "application/octet-stream")}
        requests.post(pre_url, data=form_data, files=files, headers=self._auth_headers(), verify=self.verify_ssl)

        tmp_url = f"{self.base_url}/ugreen/v1/filemgr/getUpdateTmpInfo"
        tmp_params = {
            "dir": remote_dir,
            "uuid": upload_uuid,
            "filename": remote_name,
            "action_type": "0",
            "size": str(file_size),
        }
        requests.get(tmp_url, params=tmp_params, headers=self._auth_headers(), verify=self.verify_ssl)

        upload_url = f"{self.base_url}/ugreen/v1/filemgr/fileUploadV2?"
        ug_param = json.dumps({
            "uuid": upload_uuid,
            "file_name": remote_name,
            "action_type": 0,
            "size": file_size,
            "current_size": file_size,
            "resume": True,
            "dir": remote_dir,
            "change_time": int(time.time() * 1000),
            "is_live_photo": False,
            "first_request": False,
            "begin_size": 0,
        })
        headers = {**self._auth_headers(), "ug-param": ug_param}
        resp = requests.post(upload_url, data=file_content, headers=headers, verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()


# ---------- 使用示例 ----------

if __name__ == "__main__":
    nas = UgreenNASClient(
        base_url="http://192.168.1.100:9999",
        username="admin",
        password="your-password",
    )

    nas.login()
    print("登录成功，uid:", nas.session["uid"])

    info = nas.sys_info()
    print(f"设备: {info['common']['model']}  系统版本: {info['common']['system_version']}")

    dev = nas.device_monitoring()
    print(f"CPU: {dev['cpu_usage_rate']}%  内存: {dev['ram_usage_rate']}%")

    temp = nas.temperature_monitoring()
    print(f"CPU温度: {temp['cpu_temperature']}°C  风扇: {temp['fan_speed']} RPM")

    files = nas.list_dir("/Documents")
    for f in files:
        print(f"  {f['name']}  ({f['size']} bytes)")
```

---

## curl 示例（快速调试）

### 1. 获取RSA公钥

```bash
curl -s -D - -X POST "http://192.168.1.100:9999/ugreen/v1/verify/check" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin"}' 2>&1 | grep -i x-rsa-token
```

### 2. 用 openssl 加密密码

```bash
echo "<x-rsa-token的值>" | base64 -d > public_key.pem
echo -n "your-password" | openssl rsautl -encrypt -pubin -inkey public_key.pem | base64 -w0
```

### 3. 登录

```bash
curl -s -X POST "http://192.168.1.100:9999/ugreen/v1/verify/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<加密后的密码Base64>","otp":true,"keepalive":true,"is_simple":true}'
```

### 4. 查看系统信息（使用token原文）

```bash
curl -s "http://192.168.1.100:9999/ugreen/v1/sysinfo/machine/common?token=<token原文>" | jq .
```

### 5. 列出目录（需RSA加密token）

```bash
ENCRYPTED_TOKEN=$(echo -n "<token原文>" | openssl rsautl -encrypt -pubin -inkey public_key.pem | base64 -w0)

curl -s -X POST "http://192.168.1.100:9999/ugreen/v2/filemgr/getDirFileListV2" \
  -H "Content-Type: application/json" \
  -H "x-ugreen-security-key: <token_id>" \
  -H "x-ugreen-token: $ENCRYPTED_TOKEN" \
  -H "Referer: http://192.168.1.100:9999/filemgr/?_filemgr=a58981e8" \
  -d '{"path":"","limit":2000,"page":1,"is_shield_recycle":false,"data_type":0,"sort_type":1,"reverse":false,"permission":4,"root_type":3}' | jq .
```

---

## 常见问题

**Q: 登录返回 1003 Wrong account or password?**
A: 检查用户名密码是否正确，确认RSA加密使用的是PKCS#1 v1.5（不是OAEP）。

**Q: 接口返回 1024 Authorization timeout?**
A: Token已过期，重新登录获取新token。

**Q: 文件管理接口返回认证失败？**
A: 确认使用了风格2认证头（`x-ugreen-security-key` + `x-ugreen-token`），且 `x-ugreen-token` 是用登录返回的 `public_key` 对 `token` 做RSA加密后的Base64。

**Q: 上传大文件失败？**
A: 当前示例为单分片上传，大文件需要实现分片上传逻辑（`begin_size`、`current_size`、`resume` 参数）。
