# cwkr — Community Knowledge Watch & Report

## プロジェクト概要

技術コミュニティ（llm-d・Kubernetes）の GitHub 活動を毎日自動収集し、Knowledge Graph を累積更新しながら人間が読めるサマリーを生成するパイプラインです。

- **データ収集**: GitHub Issues / PRs（REST API）
- **処理**: Claude Code CLI（`claude -p`）によるエンティティ抽出・サマリー生成
- **保存**: JSON-LD Knowledge Graph + Markdown サマリー → git push
- **実行**: ローカル PC の cron / launchd で毎日定期実行

---

## リポジトリ構成

```
cwkr/
├── CLAUDE.md                        ← このファイル
├── AGENTS.md                        ← サブエージェント設計書
├── config.yaml                      ← 監視ソース定義（ここを編集して追加）
├── setup.sh                         ← 初期セットアップ（venv + スケジューラ）
├── knowledge-graph/
│   ├── schema.jsonld                ← OWL オントロジー定義
│   └── graph.jsonld                 ← 累積 Knowledge Graph（毎日更新）
├── summaries/
│   └── YYYY/MM/YYYY-MM-DD/
│       ├── index.md
│       └── <source_id>.md
├── logs/                            ← cron ログ（.gitignore 対象）
├── scripts/
│   ├── run_daily.sh                 ← cron / launchd から呼ぶラッパー
│   ├── daily_routine.py             ← メインオーケストレーター
│   ├── sources/
│   │   ├── base.py                  ← DataSource 基底クラス + SourceItem
│   │   ├── github.py                ← GitHub アダプター
│   │   └── __init__.py              ← SOURCE_REGISTRY
│   ├── kg_updater.py                ← KG 更新（claude CLI 使用）
│   ├── summary_writer.py            ← サマリー生成（claude CLI 使用）
│   └── requirements.txt
└── .claude/
    └── settings.json                ← Claude Code プロジェクト設定
```

---

## セットアップ

```bash
# 初回セットアップ（venv 作成 + 依存インストール）
bash setup.sh

# macOS でスケジューラも設定する場合
bash setup.sh --launchd

# Linux の場合
bash setup.sh --cron

# Claude Code 認証（未済の場合）
claude login
```

### 環境変数

| 変数 | 必須 | 説明 |
|---|---|---|
| `GITHUB_TOKEN` | 任意推奨 | GitHub PAT（なければ 60 req/h、あれば 5000 req/h） |

`ANTHROPIC_API_KEY` は不要です。`claude` CLI の認証（サブスクリプション）を使います。

---

## 手動実行

```bash
# プッシュなしでテスト
scripts/run_daily.sh --no-push

# 過去 48 時間分を取得
scripts/run_daily.sh --hours 48

# 直接実行
source .venv/bin/activate
python scripts/daily_routine.py --no-push
```

---

## 新しい情報ソースの追加

`scripts/sources/` にアダプターを追加するだけで拡張できます。

```python
# scripts/sources/web_article.py の例
from .base import DataSource, SourceItem

class WebArticleSource(DataSource):
    source_type = "web_article"

    def fetch(self, since: datetime) -> list[SourceItem]:
        # RSS や スクレイピングで記事を取得
        ...
```

1. `scripts/sources/__init__.py` の `SOURCE_REGISTRY` に登録
2. `config.yaml` にブロックを追加（`type: web_article`）

---

## Knowledge Graph の利用

`knowledge-graph/graph.jsonld` は W3C 標準の JSON-LD 形式です。

```python
# rdflib での読み込み例
import rdflib
g = rdflib.ConjunctiveGraph()
g.parse("knowledge-graph/graph.jsonld", format="json-ld")

# SPARQL クエリ例
for row in g.query("SELECT ?s ?p ?o WHERE { ?s cwkr:relatedTo ?o }"):
    print(row)
```

---

## 開発時のよくある操作

```bash
# 特定ソースだけテスト（config.yaml を一時編集してソースを1つにする）
python scripts/daily_routine.py --no-push --hours 72

# KG の現状確認
python3 -c "import json; g=json.load(open('knowledge-graph/graph.jsonld')); print(len(g['@graph']), 'nodes')"

# ログ確認
tail -f logs/daily.log

# cron の動作確認（macOS）
launchctl list | grep cwkr
```

---

## アーキテクチャ判断メモ

- **claude CLI を使う理由**: ANTHROPIC_API_KEY（従量課金）の代わりにサブスクリプションを活用するため
- **JSON-LD を使う理由**: W3C 標準、SPARQL 対応、rdflib 等のツールで再利用可能
- **GitHub API を使う理由**: コミュニティ Slack の OAuth App 登録を避けるため（公開コミュニティでは非推奨）
- **累積 KG の理由**: 毎日の差分を積み上げることで時系列の知識変化を追跡できる
