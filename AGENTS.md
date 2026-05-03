# AGENTS — cwkr サブエージェント設計書

Claude Code でこのプロジェクトを開発・拡張する際のエージェント役割分担を定義します。

---

## エージェント一覧

### `data-collector`
**役割**: 外部情報ソースからデータを取得する

- 担当ファイル: `scripts/sources/`
- インターフェース: `DataSource.fetch(since: datetime) -> list[SourceItem]`
- 現在の実装: `github.py`（GitHub REST API）
- 拡張時の作業:
  1. `scripts/sources/<type>.py` を新規作成
  2. `SOURCE_REGISTRY` に登録（`__init__.py`）
  3. `config.yaml` に設定ブロック追加

**開発時の注意**:
- ネットワークアクセスが必要（GitHub API レート制限に注意）
- `SourceItem` の型定義を変えない（downstream が依存している）
- 404・403 は skip、それ以外は re-raise

---

### `kg-updater`
**役割**: `SourceItem` リストから KG ノードを抽出・マージする

- 担当ファイル: `scripts/kg_updater.py`
- 入力: `dict[str, list[SourceItem]]`
- 出力: `knowledge-graph/graph.jsonld`（上書き保存）
- Claude CLI 呼び出し: `_call_claude(prompt)` → JSON 配列を期待

**開発時の注意**:
- プロンプトが長い（Issues が多い日は数万 token）のでタイムアウト設定に注意
- `_merge_nodes` は `@id` をキーにして冪等マージ（同じ実行を何度しても安全）
- Claude の出力が JSON 配列でない場合は `_extract_json` がフォールバック処理

---

### `summarizer`
**役割**: `SourceItem` リストから Markdown サマリーを生成する

- 担当ファイル: `scripts/summary_writer.py`
- 入力: `dict[str, list[SourceItem]]`
- 出力: `summaries/YYYY/MM/YYYY-MM-DD/<source_id>.md`
- 将来: Slack / メール / Notion への配信レイヤーはここに追加する

**開発時の注意**:
- 出力フォーマットを変える場合はプロンプト（`_SUMMARY_PROMPT`）を編集
- 言語を変える場合も同様（デフォルトは英語）

---

### `orchestrator`
**役割**: 全エージェントを順番に呼び出す

- 担当ファイル: `scripts/daily_routine.py`
- フロー: config 読み込み → collect → update_graph → write_summaries → git push
- 新しいステップを追加する場合はここに追記

---

## 典型的な開発タスクとエージェントの対応

| タスク | 主担当 | 変更ファイル |
|---|---|---|
| 新しい情報ソース追加 | `data-collector` | `sources/<type>.py`, `__init__.py`, `config.yaml` |
| KG のスキーマ拡張 | `kg-updater` | `schema.jsonld`, `kg_updater.py`（プロンプト） |
| サマリーフォーマット変更 | `summarizer` | `summary_writer.py`（プロンプト） |
| 配信先追加（Slack 等） | `summarizer` | `summary_writer.py` or 新規ファイル |
| 実行スケジュール変更 | `orchestrator` | `setup.sh`（cron/plist 設定） |
| KG クエリ・可視化 | — | 別スクリプトを `scripts/` に追加 |

---

## Claude Code での作業フロー

```
# 新しいソースを追加するとき
$ claude "web_article タイプの DataSource を scripts/sources/web_article.py に実装して。
  RSS フィードを fetch する。SourceItem の仕様は sources/base.py を参照。"

# KG のスキーマを拡張するとき
$ claude "cwkr:MeetingNote という新しいクラスを schema.jsonld に追加して、
  kg_updater.py のプロンプトにも反映して。"

# デバッグ
$ claude "kg_updater.py の _merge_nodes が重複ノードを生成する原因を調査して。"
```
