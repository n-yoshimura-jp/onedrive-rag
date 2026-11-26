"""OneDrive の .md を分割・ベクトル化して、質問に近い文章を検索する"""
import json

import numpy as np
from openai import OpenAI

from onedrive_rag import config, onedrive_client

client = OpenAI()

# ファイルごとのベクトルの保存先（.gitignore 済み）
EMB_CACHE = config.BASE_DIR / ".cache" / "embeddings"


def split_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """size 文字ずつ、前後を overlap 文字重ねて分割する"""
    text = text.strip()
    chunks, start = [], 0
    while start < len(text):
        chunk = text[start : start + size].strip()
        if chunk:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for i in range(0, len(texts), 100):  # 100件ずつ送る
        res = client.embeddings.create(model=config.EMBED_MODEL, input=texts[i : i + 100])
        vectors.extend(d.embedding for d in res.data)
    return vectors


def load_file(file: dict) -> dict:
    """.md を分割・ベクトル化する。内容が変わっていなければキャッシュを使う。"""
    cache_path = EMB_CACHE / f"{file['id']}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached["etag"] == file["etag"] and cached["model"] == config.EMBED_MODEL:
            return cached

    text = onedrive_client.download(file["id"]).decode("utf-8-sig")  # BOM付きのUTF-8にも対応
    chunks = split_text(text)
    data = {
        "etag": file["etag"],
        "model": config.EMBED_MODEL,
        "name": file["name"],
        "chunks": chunks,
        "vectors": embed(chunks) if chunks else [],
    }
    # 社内文書の本文を含むので、自分だけが読み書きできるファイルにする
    EMB_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path.touch(mode=0o600, exist_ok=True)
    cache_path.chmod(0o600)  # 既存のファイルの権限もそろえる
    cache_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def search(question: str, folder: str, top_k: int = config.TOP_K) -> list[dict]:
    """フォルダ内の .md から質問に近い文章を top_k 件返す"""
    names, chunks, vectors = [], [], []
    for f in onedrive_client.list_md_files(folder):
        doc = load_file(f)
        names += [doc["name"]] * len(doc["chunks"])
        chunks += doc["chunks"]
        vectors += doc["vectors"]

    if not chunks:
        return []

    q = np.array(embed([question])[0])
    m = np.array(vectors)
    scores = m @ q / (np.linalg.norm(m, axis=1) * np.linalg.norm(q))
    best = np.argsort(scores)[::-1][:top_k]
    return [
        {"source": names[i], "text": chunks[i], "score": float(scores[i])} for i in best
    ]
