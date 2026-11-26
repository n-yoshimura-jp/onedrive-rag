# onedrive-rag

OneDrive に置いた社内文書（Markdown）をもとに、質問に答える RAG ツールです。

質問をまず OpenAI Decisions API で部署フォルダ（人事・経理・IT）に分類し、そのフォルダの文書だけを検索して回答します。分類に自信がない質問は検索せずに聞き返すため、的外れな回答を防げます。

## 処理の流れ

LangGraph のワークフローで、次の順に処理します。

```
1 質問を受け取る（receive_question）
  ↓
2 Decisions API で分類する（classify）
  ↓
確信度 ≥ 0.6 かつ other 以外？
  ├─ はい   → 3 フォルダ内を検索（retrieve）
  │           → 4 資料から回答を作成（generate）
  │           → 5 出典を付けて回答（respond）
  └─ いいえ → 聞き返す（fallback）
              → 5 回答（respond）
```

## 設計のポイント

- **分類してから検索する**：全文書をまとめて検索せず、質問を先に部署フォルダへ分類し、そのフォルダの文書だけを検索します。分類の確信度が低い質問には答えず、聞き返します。
- **OneDrive の権限は読み取り専用**：Microsoft Graph の権限は `Files.Read` だけです。トークンが漏れても、OneDrive のファイルを書き換えたり削除したりはできません。
- **アップロードは手作業**：アップロードをコードにすると `Files.ReadWrite` が必要になるため、あえて手作業にしています。人が確認・手直しした `.md` だけを置く流れにもなります。
- **社内文書を外に残さない**：回答の生成では `store=False` を指定し、OpenAI 側に文書と質問を保存しません。サインイン情報（`token_cache.json`）とベクトルのキャッシュは、自分だけが読み書きできる権限（600）で保存します。
- **ベクトル DB を使わない**：文書のベクトルはファイルごとに JSON でキャッシュし、NumPy で類似度を計算します。OneDrive のファイルの eTag が変わったときだけ作り直します。

## 使っている技術

| 用途 | 技術 |
|---|---|
| Python | 3.14（uv で管理） |
| ワークフロー | LangGraph |
| 分類 | OpenAI Decisions API |
| 文書の取得 | Microsoft Graph API + MSAL（デバイスコード認証、読み取り専用の `Files.Read`） |
| 検索 | OpenAI Embeddings + NumPy（ベクトルはローカルにキャッシュ） |
| 回答の生成 | OpenAI Responses API |
| Word・PDF の変換 | markitdown |

## 必要なもの

- macOS 14 以降（markitdown が使う onnxruntime の要件）
- [uv](https://docs.astral.sh/uv/)
- OpenAI の API キー
- 個人用 Microsoft アカウントと、Microsoft Entra に登録したアプリのクライアント ID

## セットアップ

詳しい手順は [setup_guide.txt](setup_guide.txt) を参照してください。

### 1. OneDrive にフォルダを用意する

OneDrive の直下に `RAG` フォルダを作り、その中に部署ごとのフォルダを置きます。フォルダ名は `src/onedrive_rag/config.py` の `CATEGORIES` と一致させます。

```
OneDrive/
└── RAG/
    ├── 人事/   就業規則.md, 休暇制度.md …
    ├── 経理/   経費精算マニュアル.md …
    └── IT/     VPN接続手順.md …
```

- 読み込むのは各フォルダ直下の `.md` だけです（サブフォルダや他の形式は無視します）。
- `.md` は UTF-8 で保存します。

### 2. Microsoft Entra でアプリを登録する

1. [Microsoft Entra 管理センター](https://entra.microsoft.com) の「アプリの登録」で新規登録します。アカウントの種類は「個人用 Microsoft アカウントのみ」を選びます。
2. 「認証」で「パブリック クライアント フローを許可する」を「はい」にします。
3. 「API のアクセス許可」で Microsoft Graph の委任されたアクセス許可 `Files.Read` を追加します。
4. 「アプリケーション (クライアント) ID」を控えます。

### 3. インストールする

```bash
uv sync
```

### 4. `.env` を作る

プロジェクト直下に `.env` を作り、次の 2 つを設定します。`.env` は `.gitignore` 済みです。コミットしたり、他人に渡したりしないでください。

```
OPENAI_API_KEY=sk-...
MS_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

作成したら、自分だけが読み書きできる権限にします。

```bash
chmod 600 .env
```

### 5. OneDrive との接続を確認する

```bash
uv run python -m onedrive_rag.onedrive_client
```

初回は URL とコードが表示されます。ブラウザで URL を開いてコードを入力し、サインインしてください。各フォルダの `.md` のファイル名が表示されれば成功です。2 回目以降はサインインは不要です。

## 使い方

### 質問する

```bash
uv run onedrive-rag
```

```
質問を入力してください（終了: exit）

質問> 有給休暇は何日もらえますか？

（分類: hr / 確信度: 0.93）
入社6か月後に10日付与されます [資料1]

参照: 人事 / 休暇規程.md
```

- `exit` または `quit` で終了します。
- 初回はファイルのダウンロードとベクトル化に時間がかかります。2 回目からはキャッシュを使うので速くなります。OneDrive のファイルが更新されると、そのファイルだけ自動で作り直します。
- 上の回答は出力形式の例です。実際の内容は OneDrive の文書によって変わります。

### Word・PDF を Markdown に変換する

1. プロジェクト直下の `docs/` に、OneDrive と同じフォルダ名で Word（`.docx`）・PDF を置きます。

   ```
   docs/
   ├── 人事/   就業規則.pdf, 休暇制度.docx …
   └── 経理/   経費精算マニュアル.pdf …
   ```

2. 変換します。

   ```bash
   uv run convert-to-md
   ```

   `md/人事/就業規則.md` のように、同じフォルダ構成で `md/` に保存されます。

3. `md/` の `.md` を開いて確認し、崩れていれば手で直します（下の「変換結果の確認」を参照）。
4. `md/<フォルダ名>/` の `.md` を、OneDrive の `RAG/<フォルダ名>/` にアップロードします。アップロードは手動で行ってください（ブラウザ、OneDrive アプリなど）。
5. アップロードが終わったら、元の Word・PDF を `docs/` から外します（プロジェクトの外に移すか、削除する）。

画像だけのスキャン PDF は文字を取り出せないため、スキップされます。

#### 変換結果の確認

| 元の形式 | 変換結果 |
|---|---|
| Word | 見出し・箇条書き・表がほぼそのまま Markdown になる。表の 1 行目が空の見出し行になるが、検索には影響しない |
| PDF | 崩れやすい。見出しに `#` が付かない、行の途中で改行が入る、表のセルの順番が入れ替わって次の見出しの後ろにずれ込む、などが起きる |

PDF には見出しや表の構造が残っていないため、markitdown は文字をページ上の位置の順に取り出すだけになります。表が崩れたままだと、「金額と購入方法」のような組み合わせを取り違えた回答につながるので、表は必ず直してください。元の Word があるなら、Word から変換する方が確実です。

#### 再変換による上書きに注意

`uv run convert-to-md` は `docs/` にあるファイルをすべて変換し直し、`md/` の同じ名前の `.md` を上書きします。手で直した `.md` が元に戻らないように、`docs/` には「まだ変換していない文書」だけを置いてください（手順 5）。

変換済みの文書の移動先を、プロジェクトの中のフォルダにしないでください。`.gitignore` の対象は `docs/` と `md/` だけなので、ほかのフォルダに置いた社内文書は Git に入るおそれがあります。

## 設定

設定は `src/onedrive_rag/config.py` で変更します。

| 名前 | 意味 |
|---|---|
| `ONEDRIVE_ROOT` | OneDrive 上の親フォルダ名（既定値: `RAG`） |
| `CATEGORIES` | 分類先。`folder` は OneDrive のフォルダ名、`description` は分類の判断材料 |
| `MIN_CONFIDENCE` | 分類の確信度がこれ未満なら聞き返す（既定値: 0.6） |
| `TOP_K` | 回答に使う文章の数（既定値: 5） |
| `DECISION_MODEL` / `ANSWER_MODEL` / `EMBED_MODEL` | 分類・回答・ベクトル化に使うモデル |

分類先を増やすときは、OneDrive にフォルダを作り、`CATEGORIES` に 1 項目足します。`description` を具体的に書くほど、分類の精度が上がります。

## ファイル構成

```
onedrive-rag/
├── .env                      API キーとクライアント ID（自分で作る）
├── pyproject.toml            プロジェクト設定（依存パッケージとコマンド）
├── setup_guide.txt           詳しい構築手順
├── src/onedrive_rag/
│   ├── config.py             設定と分類先フォルダ
│   ├── main.py               対話ループ（uv run onedrive-rag）
│   ├── graph.py              LangGraph のワークフロー
│   ├── retriever.py          文書の分割・ベクトル化・検索
│   ├── onedrive_client.py    OneDrive の認証とファイル取得
│   └── convert_to_md.py      Word・PDF の変換（uv run convert-to-md）
├── docs/                     まだ変換していない Word・PDF（自分で作る）
└── md/                       変換後の .md（自動で作られる。確認・手直ししてからアップロード）
```

実行すると、プロジェクト直下に次のファイルとフォルダが作られます。どちらも `.gitignore` 済みです。

- `token_cache.json`：サインイン情報。他人に渡さないでください。
- `.cache/`：文書のベクトル。

## よくあるエラー

| 症状 | 対処 |
|---|---|
| `AADSTS7000218` | Entra のアプリで「パブリック クライアント フローを許可する」が「はい」になっているか確認する |
| 「サインインに失敗しました」 | `token_cache.json` を削除して再実行し、サインインし直す |
| Graph API が `404 itemNotFound` を返す | `config.py` のフォルダ名が OneDrive のフォルダ名と一致しているか確認する（全角・半角、空白） |
| `UnicodeDecodeError` | `.md` を UTF-8 で保存し直す |
| いつも「判断できませんでした」と返る | `CATEGORIES` の `description` を具体的にする。必要なら `MIN_CONFIDENCE` を下げる |
| 「資料に記載がありません」が多い | 変換した `.md` に本文が入っているか確認する。`TOP_K` を増やす |
| PDF から変換した `.md` の見出しが消えている、表の中身の順番がばらばら | PDF からの変換の限界。手で直すか、元の Word から変換する |
| 手で直した `.md` が元に戻った | `convert-to-md` の再実行で上書きされた。変換済みの文書は `docs/` から外す |

その他のエラーは [setup_guide.txt](setup_guide.txt) の「よくあるエラーと対処」を参照してください。
