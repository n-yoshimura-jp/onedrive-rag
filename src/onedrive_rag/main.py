"""対話ループ（実行: uv run onedrive-rag）"""
from onedrive_rag.graph import build_graph


def main():
    app = build_graph()
    print("質問を入力してください（終了: exit）")
    while True:
        question = input("\n質問> ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue
        result = app.invoke({"question": question})
        print(f"\n（分類: {result['category']} / 確信度: {result['confidence']:.2f}）")
        print(result["answer"])


if __name__ == "__main__":
    main()
