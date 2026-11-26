"""設定とフォルダ（カテゴリ）の定義"""
import os
from pathlib import Path

from dotenv import load_dotenv

# プロジェクト直下（このファイルは src/onedrive_rag/config.py なので2つ上）
BASE_DIR = Path(__file__).resolve().parents[2]

# .env の内容を環境変数に読み込む（OPENAI_API_KEY は openai SDK が自動で使う）
# override=True: 同じ名前の環境変数がすでにあっても .env の値で上書きする
load_dotenv(BASE_DIR / ".env", override=True)

# --- OneDrive（Microsoft Graph API） ---
MS_CLIENT_ID = os.environ["MS_CLIENT_ID"]  # Step 2 で登録したアプリのクライアントID
ONEDRIVE_ROOT = "RAG"                       # OneDrive上の親フォルダ名

# --- OpenAI ---
DECISION_MODEL = "gpt-6-luna"           # Decisions API が対応するモデル
ANSWER_MODEL = "gpt-6.1-terra"          # 回答生成モデル
EMBED_MODEL = "text-embedding-3-small"  # ベクトル化モデル
MIN_CONFIDENCE = 0.6                    # 確信度がこれ未満なら聞き返す
TOP_K = 5                               # 回答に使う文章の数

# --- 振り分け先フォルダ ---
# キー: Decisions APIに渡す値 / folder: OneDrive上のフォルダ名 / description: 判断材料
CATEGORIES = {
    "hr": {
        "folder": "人事",
        "description": "就業規則、休暇、勤怠、給与、評価、福利厚生に関する質問",
    },
    "accounting": {
        "folder": "経理",
        "description": "経費精算、請求書、支払い、予算に関する質問",
    },
    "it": {
        "folder": "IT",
        "description": "PC、アカウント、パスワード、VPN、ソフトウェアに関する質問",
    },
}
