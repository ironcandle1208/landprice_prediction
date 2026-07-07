# プロジェクト構造

最終更新: 2026-07-07

```
landprice_prediction/
├── .gitignore                 # Git除外設定
├── CLAUDE.md                  # Claude Code向けプロジェクト指示
├── AGENTS.md                  # エージェント向け指示
└── docs/
    ├── project-structure.md   # 本ファイル
    ├── issue/
    │   └── template.md        # イシュー記録のテンプレート
    └── plan/
        ├── template.md              # 開発計画のテンプレート
        ├── implementation-plan.md   # 実装計画（地価×駅距離×乗降客数 分析・予測マップ）
        └── test/
            ├── preprocessing.feature   # 前処理のテストシナリオ（Gherkin・設計ドキュメント）
            └── inference-api.feature   # 推論APIのテストシナリオ（Gherkin・設計ドキュメント）
```

## 備考

- `test/` 配下の `.feature` ファイルは実行しない設計ドキュメント。pytestのテストリストとして使用する（詳細は実装計画の「テスト方針」参照）
- ソースコード（前処理・ML・フロント・Terraform）は未着手。実装開始時に本ファイルを更新すること
