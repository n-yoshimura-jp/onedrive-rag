"""OneDrive（Microsoft Graph API）から .md ファイルを取得する

- 認証: MSAL の device code flow（個人用 Microsoft アカウント）
  初回のみブラウザでサインイン。トークンを TOKEN_CACHE に保存し、2回目以降は自動で再利用する
- 一覧: /me/drive/root:/{フォルダパス}:/children
- 取得: /me/drive/items/{item-id}/content
"""
from urllib.parse import quote

import msal
import requests

from onedrive_rag import config

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.Read"]  # 読み取りのみ

# トークンの保存先（.gitignore 済み。他人に渡さないこと）
TOKEN_CACHE = config.BASE_DIR / "token_cache.json"


def get_token() -> str:
    # 保存済みのトークンがあれば読み込む
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE.exists():
        TOKEN_CACHE.chmod(0o600)  # 自分だけが読み書きできる権限にそろえる
        cache.deserialize(TOKEN_CACHE.read_text())

    # consumers = 個人用 Microsoft アカウント向け
    app = msal.PublicClientApplication(
        config.MS_CLIENT_ID,
        authority="https://login.microsoftonline.com/consumers",
        token_cache=cache,
    )

    # 保存済みのトークンで取得を試みる（期限切れなら refresh token で自動更新される）
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None

    # 取得できなければ device code flow で認証（表示された URL をブラウザで開き、コードを入力）
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"サインインを開始できませんでした: {flow.get('error_description')}")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)

    # トークンが新しくなっていれば保存（自分だけが読み書きできるファイルにする）
    if cache.has_state_changed:
        TOKEN_CACHE.touch(mode=0o600, exist_ok=True)
        TOKEN_CACHE.write_text(cache.serialize())

    if "access_token" not in result:
        raise RuntimeError(f"サインインに失敗しました: {result.get('error_description')}")
    return result["access_token"]


def list_md_files(folder: str) -> list[dict]:
    """RAG/<folder> 直下の .md ファイル（id, name, eTag）を返す"""
    # 日本語のパスは URL エンコードする
    path = quote(f"{config.ONEDRIVE_ROOT}/{folder}")
    url = f"{GRAPH}/me/drive/root:/{path}:/children"
    headers = {"Authorization": f"Bearer {get_token()}"}

    files = []
    while url:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        for item in data["value"]:
            # フォルダと .md 以外のファイルは対象外
            if "file" in item and item["name"].lower().endswith(".md"):
                files.append({"id": item["id"], "name": item["name"], "etag": item["eTag"]})
        url = data.get("@odata.nextLink")  # 件数が多いと次のページの URL が返る
        # トークンを Graph 以外に送らないよう、次のページの URL を確認する
        if url and not url.startswith(f"{GRAPH}/"):
            raise RuntimeError(f"想定外の次ページの URL です: {url}")
    return files


def download(item_id: str) -> bytes:
    """ファイルの中身を取得する"""
    r = requests.get(
        f"{GRAPH}/me/drive/items/{item_id}/content",
        headers={"Authorization": f"Bearer {get_token()}"},
        timeout=60,
    )
    r.raise_for_status()
    return r.content


if __name__ == "__main__":
    # 接続テスト: uv run python -m onedrive_rag.onedrive_client
    for cat in config.CATEGORIES.values():
        print(f"[{cat['folder']}]")
        for f in list_md_files(cat["folder"]):
            print("  -", f["name"])
