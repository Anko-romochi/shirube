# SHIRUBE 1.0.0

Codex向けの「主張と根拠の地図」。原文引用、確認範囲、原典系列、未解決矛盾、次に読む資料、前回の結論との差分を記録します。

機械が確認するのは保存文と形式の整合です。意味的な支持、史実、原典の相互独立性を保証しません。申告状態と引用リンクの意味レビュー記録を分けて表示します。

## はじめる

リリースのSkill ZIPを展開し、`shirube`を対象プロジェクトの`.agents/skills/`へ配置します。既存同名フォルダは退避してから更新してください。Codexで`$shirube`を指定します。検索・閲覧は環境の利用可能なツールを使い、Python helperはローカル形式照合のみを行います。

[導入・使い方・終了コード](skills/shirube/README.md) / [Skill本体](skills/shirube/SKILL.md) / [台帳契約](skills/shirube/references/ledger.md) / [参考元と比較の限界](skills/shirube/references/upstream.md)

Python 3.10以上、標準ライブラリのみ。repoルートでの動作例:

```text
python skills/shirube/scripts/evidence.py skills/shirube/examples/ledger.json sample-output
python -B -m unittest discover -s skills/shirube/tests -v
```

架空例は全てfictionalです。実際の調査レポートの全記録には非公開情報や絶対パスを含む場合があります。共有前に資料の権利と内容を確認してください。

## 参考元・ライセンス

[MaryCache/imozuru](https://github.com/MaryCache/imozuru)の原典へたどる探索設計を参照。固定commitは`14635fb74a1f68e5c138379c3a6e4ec823b7cb59`。上流にも引用照合や矛盾併記があります。SHIRUBEの文章・コード・テストは新規実装です。上流コードを実行した性能比較は未実施であり、性能優位を主張しません。

MIT。新規実装はLICENSE、参考元の表記はUPSTREAM-LICENSE.txt。公開対象はRELEASE_ALLOWLIST.jsonの汎用Skill・コード・テスト・架空例・説明のみです。
