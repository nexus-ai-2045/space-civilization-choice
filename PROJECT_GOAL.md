---
title: 宇宙文明の選択権 プロジェクトゴール
type: project-goal
status: active
created: 2026-08-24
updated: 2026-08-28
owner: repository-maintainers
project: space-civilization-choice
canonical_repository: nexus-ai-2045/space-civilization-choice
goal_id: space-civilization-choice-mvp-v1
---

# プロジェクトゴール

## ゴール

2026年の日本を起点に、技術投資の選択が2040年の「宇宙文明の選択権」へ与える影響を、
同一条件からの三分岐で比較し、事実・シナリオ仮説・モデル仮定・未知を分離したまま、
結果から原因と証拠へ遡れる公開MVPを完成させる。

「宇宙文明の選択権」は、月面文明の完成や国家の優劣を意味しない。技術、統治、文化、
対外関係を、一つの国家・企業・標準へ全面的に固定されずに選び直せる余地を指す。

## メタ安全保障との関係

守る対象は、単独の装置や月面基地ではなく、日本が将来も選択を変更できる能力である。
地球上の資金、知財、人材、標準の選択が、宇宙での到達・運用・統治条件へ波及し、その結果が
日本の産業、同盟、社会的正統性へ戻る一本の因果連鎖を観測する。

ハッカソンMVPでは、二つの出発領域を**宇宙 × 認知・文化**に固定する。日本社会が宇宙進出へ
与える意味、期待、不安が、人材・予算・企業投資を通じて物理的な宇宙能力を変え、その成功、
依存、事故が再び社会の認識と支持を変える循環を、AIエージェント間の相互作用として観測する。
固定された方針名を選ぶことではなく、利用者が具体的な資源配分と制約を変更し、介入点と
選択肢喪失条件を探索できることを中核価値とする。

## スコープ

- 2026年の公開情報から作る版管理された`scenario_snapshot`
- 一つの追加重点枠と、国際統合型・国内自立型・開放基盤型の三分岐
- `2026 → 2030 → 2035 → 2040`の四ラウンド
- 物理・物質、経済・産業・組織、認知・文化・意味から、一本の連鎖を検証するMVP最小接続
- 宇宙 × 認知・文化を二つの出発領域とし、経済・組織を両者の伝達経路とする
- 予算配分、依存、公開度、人材、外部shockを変更して反復実行できるparameterized simulation
- 六観測軸、モデル内部遷移trace、研究根拠台帳、model card、run manifest
- LLMなしで再生できる決定論的コア。外部AI接続はMVP coreに含めず、ADR-0009に従う後続の別process bounded JSON/HTTP adapterへ延期する
- 深い不確実性下で、単一予測ではなく脆弱性、後悔、選択肢保持を比較する方法

## 非目標

- 2040年、日本政府、企業、国際秩序を予言すること
- 軍事作戦、攻撃、情報工作を最適化すること
- 文明、国家、技術ツリーを単一総合点で序列化すること
- 実在組織・人物の非公開意図を推測すること
- LLMの文章を証拠または状態遷移の正本にすること
- 人間の価値判断を自動的な政策提言へ置き換えること

## 実行契約

比較runでは、`scenario_snapshot_hash`、`seed`、`model_version`、
`exogenous_event_stream_hash`を三分岐で固定する。変更できる主要因は最初に選ぶ技術ツリーと、
その選択を入力としてモデル規則が生成するエージェント行動だけとする。分岐内で生じる行動と
状態遷移を含む全event logは分岐ごとに保存し、各分岐の`event_log_hash`で同一性を検証する。
各差分は`turn_id`、入力、行動、規則、`evidence_ref`へ遡れること。このtraceはモデル内部の
遷移由来を示し、実世界の因果推定または因果証明を意味しない。

各review時点では、確認できた現在状態を取り込み、残り期間の分岐を再評価する。これは
モデル予測制御（Model Predictive Control; MPC）に着想を得た逐次更新型の適応計画である。
予測モデル、有限horizonの目的、制約付き反復最適化、観測更新、先頭行動だけの適用を実装するまでは
「MPCを実装した」と表現しない。安定性はMPCの定義ではなく、別途検証する保証項目として扱う。

組合せ爆発は、XLRM（外生的不確実性、政策levers、関係、評価尺度）、有限の因子集合、run budget、
整合しない組合せの除外、因子の予備選別、重要な脆弱性条件の発見という順序で抑える。
説明性を失う圧縮だけで次元を減らさず、budgetとsampling設計がない段階では「回避済み」と表現しない。

## 完了条件

以下はプロダクトMVPの完了条件であり、文書設計や公開準備の完了条件とは分離する。
完了へ変更する項目は`[x]`にし、同じ行へrepo内の一次証拠をMarkdown linkで付ける。
最初の完了項目が生じたらfront matterの`status`を`active`へ、全項目が完了したら
`complete`へ変更する。契約検査は、未完了の設計とプロダクト完成を別状態として返す。

- [ ] `GOAL-001`: 本文書、README、プロダクト仕様のゴール・非目標・ownerが矛盾しない
- [x] `REPLAY-001`: [receipt](evidence/done-when/REPLAY-001.json) 同一のsnapshot hash、seed、model versionを二回実行し、canonical output hashが一致する
- [ ] `BRANCH-001`: 三分岐が同一snapshot hash、seed、exogenous event stream hashから生成され、分岐固有の全event logがそれぞれのevent log hashで検証できる
- [x] `TRACE-001`: [receipt](evidence/done-when/TRACE-001.json) 六軸の各deltaをturn ID、入力、行動、モデル規則、evidence refへ遡れ、実世界の因果とモデル内部遷移を区別できる
- [ ] `CLASS-001`: 全claim／提案に`record_kind`、`epistemic_class`、`provenance_type`、`validation_state`があり、不整合な組合せが0になる
- [ ] `MODEL-001`: 全数値係数に単位、範囲、根拠、更新式、感度、反証条件がある
- [ ] `ROBUST-001`: XLRM、performance threshold、ensemble manifest、robustness／regret定義を固定し、脆弱性条件と選択肢喪失条件をholdoutで再確認できる
- [ ] `FEEDBACK-001`: 各評価runにowner、判定、next action、resume condition、evidenceがある
- [ ] `HUMAN-001`: 15〜25分の比較体験とモデル内因果の説明可能性を、人間レビュー記録で確認する
- [ ] `CI-001`: exact HEADでreplay、schema、trace、goal contract、security gateのCIが成功する（GitHub rulesetを実行時SSOTとし、同一commit内receiptによる自己証明はしない）
- [ ] `PUBLIC-001`: 公開前レビュー後に、README、license、SECURITY、secret／個人path scan、公開read-backを確認する

## 現在の達成状態

- `status`: active
- Phase 1の一分岐fixture、決定論的replay、model_internal trace、exact HEAD CI receiptを実装済み
- ハッカソンdemo sliceとしてローカル適応型シミュレーター（Causal Constellation）を実装中
- BRANCH-001の三分岐比較完成、model card、感度分析、完成版UI、人間評価は未実装
- 上記チェック項目は、対応する一次証拠が揃うまで未完了のまま保持する

## 最小PDCAとフィードバックループ

1. **Plan**: 仮説、観測軸、許容範囲、snapshot、seed、ownerを固定する。
2. **Do**: LLMなしのfixtureを実行し、manifest、canonical JSON、event logを保存する。
3. **Check**: replay hash、三分岐の共通条件、モデル内因果trace、分類、感度、脆弱性を検査する。
4. **Act**: 失敗を文言で覆わず、model card、fixture、test、ADR、または本ゴールの該当契約へ戻す。

旧runは上書きしない。feedback項目は`owner`、`next_action`、`resume_condition`、`evidence`を
持ち、解決、移管、棄却のどれかになるまで残す。

## 外部境界

commit、push、PR、merge、repository visibility変更、公開、応募、外部送信は、それぞれ独立した
承認・検証境界として扱う。ローカルgateの通過は、これらの承認を意味しない。

## 戻り先

- ゴール・非目標・完了条件の変更: 本文書と必要なADR
- シナリオ事実・仮説・未知の変更: `docs/RESEARCH_EVIDENCE.md`
- 状態・分岐・replay契約の変更: `docs/SIMULATION_DESIGN.md`
- 実装順とphase判定の変更: `docs/ROADMAP.md`
- 公開・運用境界の変更: `PREFLIGHT.md`、`PUBLIC_READY.md`、`docs/OPERATIONS.md`
