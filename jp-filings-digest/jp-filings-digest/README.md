# jp-filings-digest

作成者：櫻田　昊介

日本の会社がEDINETに出す書類（TOB・大量保有報告書・臨時報告書・自己株買い）を、毎営業日AIで英語の事実要約にし、サイト・RSS・週1のメール原稿として出す仕組みです。英語の書類を出していない会社には「No English filing」の印が付きます。

## 動きの流れ

1. 毎営業日18:30（日本時間）にGitHub Actionsが起動する
2. EDINET API（公式）からその日の書類一覧を取る
3. 対象の書類だけ選び、英語の書類がない会社とTOBを先に並べる（上限は1日150件）
4. 書類のCSVを取り、Claude Haiku 5.5で英語の事実要約にする
5. 売買の勧めに当たる言葉が出たら、作り直させる。それでも出たら公開せず、Actionsの実行結果（needs-review）にだけ残す
6. `docs/` にサイトとRSSを書き出し、GitHub Pagesで公開する
7. 毎週月曜8:00に、無料ニュースレター用の原稿を `docs/weekly/` に作る

## 始め方（あなたがやること）

1. **EDINETのAPIキーを取る**：EDINETのAPI利用登録で無料で発行されます。
2. **AnthropicのAPIキーを取る**：platform.claude.com でキーを作り、使いすぎ防止の月額上限（例：10ドル）を設定します。
3. **GitHubにこのフォルダを置く**：新しいリポジトリを作り、中身をすべてアップロードします。
4. **秘密の値を登録する**：Settings → Secrets and variables → Actions
   - Secrets：`EDINET_API_KEY`、`ANTHROPIC_API_KEY`
   - Variables（`OPERATOR_NAME` は必須。PDL1.0で加工者名の表示が要るため、未設定だと止まります）：`SITE_URL`（例 `https://<ユーザー名>.github.io/jp-filings-digest`）、`OPERATOR_NAME`（サイトに出す運営者名）、`CONTACT_EMAIL`、`SUBSCRIBE_URL`（ニュースレターの登録ページ）
5. **GitHub Pagesを有効にする**：Settings → Pages → Branch `main` / フォルダ `/docs`
6. **一度手で動かす**：Actions → daily-digest → Run workflow。できたページを開き、原文と10件ほど見比べます。
7. **ニュースレターを用意する**：Substackなど無料で始められるサービスに英語のニュースレターを作り、`docs/weekly/` の原稿を毎週貼って送ります（5分ほど）。

## 手元での試し方

```
python -m digest.run --mock --date 2026-11-05 --out demo   # 架空のサンプルで動かす（API不要）
python -m digest.run --weekly --date 2026-11-05 --out demo # 週1原稿を作る
python -m pytest -q                                         # テスト
```

外部ライブラリは不要です（Python 3.10以上の標準機能だけで動きます。テストにはpytestを使います）。

## 守ること

- EDINETの内容は公共データ利用規約（PDL1.0）で使っています。出典と「AIで加工した」ことをすべてのページに出しています。この表示は消さないでください。
- EDINETのサイトをスクレイピングしないでください（規約で禁止）。必ずAPIを使います。
- 事実の要約だけを出し、売買の勧め・評価・予想は書きません。有料版を始める前に、関東財務局（理財部証券監督第2課）に「投資助言業の登録が要らないか」を確かめてください。
- TDnet（適時開示）の内容は使いません。再配信には月23万円以上の契約が必要です。

## 設定を変える

| 変数 | 既定値 | 意味 |
| --- | --- | --- |
| `MAX_DOCS` | 150 | 1日に要約する上限 |
| `MODEL` | claude-haiku-5-5 | 要約に使うモデル（1件の返答は最大2,000トークン） |
| `REQUEST_INTERVAL_SEC` | 3 | EDINETへの取得の間隔（秒） |
| `MAX_INPUT_CHARS` | 12000 | 1件あたりAIに渡す文字数の上限 |

対象の書類の種類は `digest/config.py` の `DOC_TYPES` で変えられます。
