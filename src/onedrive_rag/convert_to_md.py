"""docs/ 内の Word・PDF を Markdown に変換して md/ に保存する

実行: uv run convert-to-md
docs/人事/就業規則.pdf → md/人事/就業規則.md のように、フォルダ構成はそのまま保つ。
"""
from pathlib import Path

from markitdown import MarkItDown

# プロジェクト直下（このファイルは src/onedrive_rag/convert_to_md.py なので2つ上）
BASE_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = BASE_DIR / "docs"  # 変換前のファイル
OUT_DIR = BASE_DIR / "md"    # 変換後の .md
SUPPORTED = {".docx", ".pdf"}


def main():
    if not SRC_DIR.is_dir():
        raise SystemExit(f"{SRC_DIR} がありません。docs/<フォルダ名>/ に Word・PDF を置いてください")

    converter = MarkItDown()
    for src in sorted(SRC_DIR.rglob("*")):
        if src.suffix.lower() not in SUPPORTED:
            continue

        # ローカルのファイルだけを変換する（URL は扱わない）
        text = converter.convert_local(src).markdown
        if not text.strip():
            print(f"スキップ（文字を取り出せません。画像だけのPDF？）: {src.relative_to(SRC_DIR)}")
            continue

        out = OUT_DIR / src.relative_to(SRC_DIR).with_suffix(".md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"変換しました: {src.relative_to(SRC_DIR)} → {out.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
