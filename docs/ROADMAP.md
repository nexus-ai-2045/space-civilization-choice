# ロードマップ

全phaseの上位ゴールとdone_whenは[`PROJECT_GOAL.md`](../PROJECT_GOAL.md)を正本とする。
phase完了はプロダクトMVP完了、公開承認、merge承認を意味しない。

## Phase 0: 公開設計

- 一枚設計、仕様、ADR、根拠台帳、安全境界
- 公開前gateと人間レビュー
- 採用level、固定版、証拠、drift方針をmanifest化しrequired CIで検査

完了条件: 事実・仮説・未知が分離され、未実装を明記し、secret・個人path・権利境界を確認する。

## Phase 1: 決定論的fixture

- branch-neutral状態schema、国内自立型fixture、5エージェント、4ラウンド
- 上書き拒否するJSONL event log
- 同一seedのreplay test

完了条件: LLMなしで一分岐を再生でき、状態差分をturn IDへ遡れる。

状態: **完了条件達成**。国内自立型の一分岐・4ラウンドfixture、上書き拒否するJSONL event log、同一入力の
canonical hash一致、六軸deltaのmodel_internal traceまで実装済み。完了はMVP完成や公開承認を意味しない。
branch-neutral schemaの固定とmodel card初版はPhase 2着手前に行う。

## Phase 2: 残る二分岐と三分岐比較

- 共通外生イベント列
- 六観測軸と感度分析
- 反実仮想link

完了条件: 同一snapshotとseedから三分岐を比較できる。

追加条件: 三分岐が同じ`exogenous_event_stream_hash`を共有し、分岐固有の全event logを
それぞれの`event_log_hash`で検証できる。さらにfactor inventory、予備スクリーニング、
少なくとも一つの脆弱性条件を再現可能なfixtureで説明できる。

## Phase 3: UI

- 3つの視覚コンセプトを作成し、人間が選択
- シナリオ設定、分岐比較、モデル内因果トレース、証拠台帳
- keyboard、mobile、reduced motion検証

完了条件: 利用者が重要な結果差から原因と根拠へ戻れる。

## Phase 4: 限定LLM導入

- 単一エージェントの構造化行動提案
- 許可行動・予算・schema検証
- prompt injection、再試行、費用、棄却のeval

完了条件: LLMを無効化してもsimulation coreが再生でき、LLMが状態を直接変更できない。

## Phase 5: ハッカソンdemo評価

- 専門家レビュー、ユーザーテスト、説明可能性eval
- demo fixtureと失敗例
- exact HEADのCIと公開物レビュー

完了条件: 15〜25分の体験で、結末ではなくモデル内因果とトレードオフを説明できる。

### 2026-08-29 demo vertical slice

時間制約下のハッカソン実演に限り、Phase 2の三分岐、Phase 3の最小比較画面、Phase 4の単一AI提案を
縦切りで前倒しする。決定論コアを実行権威とし、AI障害時にも同じ入力から完走する。これは各Phaseの
完全な完了や公開deployを意味しない。現在の判断境界は[ADR-0009](adr/0009-local-first-adaptive-simulation-engine.md)を正本とする。

外部AIを必須とする判断は[ADR-0009](adr/0009-local-first-adaptive-simulation-engine.md)で置き換えた。
現在の実装正本はローカル決定論provider、5主体PDCA、parameter registry、三相traceであり、Google Cloud等は
このcontractへ接続する後続deployment laneとする。

## 各phase共通の最小PDCA

1. Plan: 対象done_when ID、仮説、owner、入力hash、許容範囲を固定する。
2. Do: 最小fixtureまたは文書検査を実行し、成果物を版管理する。
3. Check: test、hash、trace、根拠分類、人間レビューの該当証拠を確認する。
4. Act: 失敗をmodel card、fixture、test、ADR、goal contractの適切な戻り先へ反映する。

「通ったこと」だけでなく、失敗、未知、次の一手、再開条件もfeedbackとして保持する。
