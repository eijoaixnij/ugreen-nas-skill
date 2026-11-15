#!/usr/bin/env python3
"""
绿联NAS (UGOS Pro) API 客户端 - 可独立运行或作为模块导入
依赖: requests pycryptodome
"""
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
    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = False):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session: Optional[dict] = None
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @staticmethod
    def _rsa_encrypt_base64(plaintext: str, public_key_pem: str) -> str:
        key = RSA.import_key(public_key_pem)
        return base64.b64encode(PKCS1_v1_5.new(key).encrypt(plaintext.encode())).decode()

    def _get_rsa_public_key(self) -> str:
        resp = requests.post(f"{self.base_url}/ugreen/v1/verify/check",
                             json={"username": self.username}, verify=self.verify_ssl)
        token = resp.headers.get("x-rsa-token")
        if not token:
            raise RuntimeError("响应头中未找到 x-rsa-token")
        if "BEGIN" not in token:
            token = base64.b64decode(token).decode()
        return token

    def login(self) -> dict:
        rsa_pubkey = self._get_rsa_public_key()
        encrypted_pwd = self._rsa_encrypt_base64(self.password, rsa_pubkey)
        resp = requests.post(f"{self.base_url}/ugreen/v1/verify/login", json={
            "username": self.username, "password": encrypted_pwd,
            "otp": True, "keepalive": True, "is_simple": True,
        }, verify=self.verify_ssl)
        data = resp.json()
        if data["code"] != 200:
            raise RuntimeError(f"登录失败: {data.get('msg')} (code={data['code']})")
        self.session = {
            "token_id": data["data"]["token_id"],
            "token": data["data"]["token"],
            "uid": data["data"]["uid"],
            "public_key": data["data"]["public_key"],
        }
        return self.session

    def _auth_headers(self) -> dict:
        if not self.session:
            raise RuntimeError("未登录")
        enc = self._rsa_encrypt_base64(self.session["token"], self.session["public_key"])
        return {"x-ugreen-security-key": self.session["token_id"], "x-ugreen-token": enc}

    # --- 系统监控 ---
    def sys_info(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/sysinfo/machine/common?token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    def device_monitoring(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/desktop/components/data?id=desktop.component.DeviceMonitoring&token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    def temperature_monitoring(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/desktop/components/data?id=desktop.component.TemperatureMonitoring&token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    def storage_space(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/desktop/components/data?id=desktop.component.StorageSpace&token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    def system_status(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/desktop/components/data?id=desktop.component.SystemStatus&token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    def priority_link(self) -> dict:
        return requests.get(f"{self.base_url}/ugreen/v1/user/priority_link?token={self.session['token']}",
                            verify=self.verify_ssl).json()["data"]

    # --- 文件管理 ---
    def list_dir(self, path: str = "", root_type: int = 3) -> list:
        resp = requests.post(f"{self.base_url}/ugreen/v2/filemgr/getDirFileListV2", json={
            "path": path, "limit": 2000, "page": 1, "is_shield_recycle": False,
            "data_type": 0, "left_no_page_show": False, "left_count": 5000,
            "sort_type": 1, "reverse": False, "permission": 4, "root_type": root_type,
        }, headers={**self._auth_headers(), "Content-Type": "application/json",
                    "Referer": f"{self.base_url}/filemgr/?_filemgr=a58981e8"}, verify=self.verify_ssl)
        return resp.json()["data"].get("right_files", {}).get("files", [])

    def mkdir(self, path: str, recursive: bool = True):
        requests.post(f"{self.base_url}/ugreen/v2/filemgr/createFolder",
                      json={"path": path, "no_recursive_creation": not recursive},
                      headers={**self._auth_headers(), "Content-Type": "application/json"},
                      verify=self.verify_ssl)

    def copy(self, src, dst: str, action: str = "skip"):
        self._cp_mv(src, dst, False, action)

    def move(self, src, dst: str, action: str = "skip"):
        self._cp_mv(src, dst, True, action)

    def _cp_mv(self, src, dst: str, move: bool, action: str):
        am = {"skip": 0, "overwrite": 1, "keep-both": 3}
        requests.post(f"{self.base_url}/ugreen/v2/filemgr/cpOrMvPath", json={
            "src": src if isinstance(src, list) else [src], "dst": dst,
            "action_type": am[action], "type": move, "intranet_share_id": 0,
        }, headers={**self._auth_headers(), "Content-Type": "application/json"}, verify=self.verify_ssl)

    def rename(self, path: str, new_name: str):
        requests.post(f"{self.base_url}/ugreen/v2/filemgr/rename",
                      json={"path": path, "new_name": new_name},
                      headers={**self._auth_headers(), "Content-Type": "application/json"}, verify=self.verify_ssl)

    def delete(self, paths, forever: bool = False):
        requests.post(f"{self.base_url}/ugreen/v2/filemgr/delPaths",
                      json={"paths": paths if isinstance(paths, list) else [paths], "forever": forever},
                      headers={**self._auth_headers(), "Content-Type": "application/json"}, verify=self.verify_ssl)

    def download(self, remote_path: str, local_path: str):
        requests.post(f"{self.base_url}/ugreen/v1/filemgr/detectionPermissions",
                      json={"paths": [remote_path], "type": 4, "intranet_share_id": 0},
                      headers={**self._auth_headers(), "Content-Type": "application/json"}, verify=self.verify_ssl)
        token_resp = requests.get(f"{self.base_url}/ugreen/v2/filemgr/getDownloadToken",
                                  params={"paths": remote_path, "intranet_share_id": "0", "coding": "true"},
                                  headers=self._auth_headers(), verify=self.verify_ssl)
        dl_url = f"{self.base_url}{token_resp.json()['data']['dl_url']}"
        with requests.get(dl_url, headers=self._auth_headers(), verify=self.verify_ssl, stream=True) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

    def upload(self, local_path: str, remote_dir: str, remote_name: Optional[str] = None):
        if remote_name is None:
            remote_name = os.path.basename(local_path)
        with open(local_path, "rb") as f:
            content = f.read()
        size = len(content)
        md5 = hashlib.md5(content).hexdigest()
        up_uuid = f"{uuid.uuid4()}_1_{md5}"
        ts = int(time.time() * 1000)
        # 预上传
        requests.post(f"{self.base_url}/ugreen/v1/filemgr/fileUpload",
                      data={"uuid": up_uuid, "dir": remote_dir, "action_type": "0", "size": str(size),
                            "begin_size": "0", "current_size": "0", "change_time": str(ts),
                            "filename": remote_name, "resume": "true", "first_request": "true"},
                      files={"file": (remote_name, b"", "application/octet-stream")},
                      headers=self._auth_headers(), verify=self.verify_ssl)
        # 临时信息
        requests.get(f"{self.base_url}/ugreen/v1/filemgr/getUpdateTmpInfo",
                     params={"dir": remote_dir, "uuid": up_uuid, "filename": remote_name,
                             "action_type": "0", "size": str(size)},
                     headers=self._auth_headers(), verify=self.verify_ssl)
        # 上传内容
        ug_param = json.dumps({"uuid": up_uuid, "file_name": remote_name, "action_type": 0,
                               "size": size, "current_size": size, "resume": True, "dir": remote_dir,
                               "change_time": ts, "is_live_photo": False, "first_request": False, "begin_size": 0})
        resp = requests.post(f"{self.base_url}/ugreen/v1/filemgr/fileUploadV2?",
                             data=content, headers={**self._auth_headers(), "ug-param": ug_param},
                             verify=self.verify_ssl)
        assert resp.json()["code"] == 200, resp.json()


def print_status_report(client: UgreenNASClient):
    """打印NAS状态报告"""
    info = client.sys_info()
    dev = client.device_monitoring()
    temp = client.temperature_monitoring()
    net = client.priority_link()

    print("=" * 50)
    print(f"  {info['common']['nas_name']} ({info['common']['model']})")
    print("=" * 50)
    print(f"  系统版本: {info['common']['system_version']}")
    print(f"  序列号:   {info['common']['serial']}")
    print(f"  运行时长: {info['common']['run_time']} 秒")
    print(f"  启动时间: {info['common']['last_turn_on_time']}")
    print("-" * 50)
    print(f"  CPU 使用率: {dev['cpu_usage_rate']}%")
    print(f"  内存使用率: {dev['ram_usage_rate']}%")
    print(f"  上传速度:   {dev['upload_speed']['value']} {dev['upload_speed']['unit']}")
    print(f"  下载速度:   {dev['download_speed']['value']} {dev['download_speed']['unit']}")
    print("-" * 50)
    print(f"  CPU 温度: {temp['cpu_temperature']}°C")
    print(f"  风扇转速: {temp['fan_speed']} RPM")
    if temp.get("disk_list"):
        for d in temp["disk_list"]:
            print(f"  硬盘 {d.get('name','?')}: {d.get('temperature','?')}°C")
    print("-" * 50)
    print(f"  主机IP:   {net['host']}")
    print(f"  HTTP端口: {net['http_port']}")
    print(f"  HTTPS端口:{net['https_port']}")
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="绿联NAS API 客户端")
    parser.add_argument("--url", required=True, help="NAS地址，如 http://192.168.1.100:9999")
    parser.add_argument("--user", required=True, help="用户名")
    parser.add_argument("--password", required=True, help="密码")
    parser.add_argument("--status", action="store_true", help="打印系统状态报告")
    parser.add_argument("--list", metavar="PATH", help="列出指定目录内容")
    parser.add_argument("--download", nargs=2, metavar=("REMOTE", "LOCAL"), help="下载文件")
    parser.add_argument("--upload", nargs=2, metavar=("LOCAL", "REMOTE_DIR"), help="上传文件")
    args = parser.parse_args()

    nas = UgreenNASClient(args.url, args.user, args.password)
    nas.login()

    if args.status:
        print_status_report(nas)
    elif args.list is not None:
        files = nas.list_dir(args.list)
        for f in files:
            ftype = "DIR " if f.get("type") == "dir" else "FILE"
            print(f"  {ftype}  {f['name']:40s}  {f.get('size', 0):>12} bytes")
    elif args.download:
        nas.download(args.download[0], args.download[1])
        print(f"已下载: {args.download[0]} -> {args.download[1]}")
    elif args.upload:
        nas.upload(args.upload[0], args.upload[1])
        print(f"已上传: {args.upload[0]} -> {args.upload[1]}/")
    else:
        print("登录成功。使用 --status 查看状态，--list PATH 列出文件，--download/--upload 传输文件。")
