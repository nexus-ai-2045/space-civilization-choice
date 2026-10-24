# ADR-0009: ローカル優先の適応型シミュレーションエンジンを正本にする

- Status: accepted
- Date: 2026-08-29
- Supersedes: ADR-0008のOpenAI固有接続判断

## Context

ハッカソンMVPは、外部AIの可用性や課金状態に依存せず、利用者が具体的なparameterを変更して
5主体×4ラウンドの相互作用を再現できなければならない。外部modelは将来Google Cloud等で実行する
可能性があるが、providerが状態遷移の正本になると、再現性、因果trace、失敗時完走を保証できない。

20入力を全直積すると探索空間が急増する。既存のNexus運用基盤には、hard constraintを先に適用し、
少数候補を評価して一手だけ実行し、証拠を再観測して計画し直す契約がある。一方、各repoの運用固有
scoreや独自ライセンスの実装を、公開シミュレーターへコピーしてはならない。

## Decision

1. `space-civilization-choice`をparameter registry、action catalog、agent role、transition ruleの正本とする。
2. 標準decision engineはローカルの`DeterministicProposalProvider`とし、同一入力とseedで再現する。
3. MVP coreのprovider registryは`DeterministicProposalProvider`だけを許可する。任意のPython objectを
   providerとして実行しない。
4. 各ラウンドをPlan、Do、Check、Actに分け、5主体の提案を検証・調停してからコアが遷移する。
5. 残りhorizonを少数候補で再評価し、先頭portfolioだけを適用して次ラウンドで再観測する。
6. これはMPCに着想を得た逐次再計画であり、連続最適化や安定性保証を備えるMPCとは称さない。
7. 20入力の自動探索は直積せず、局所感度、Top-K候補、最大3 stress scenarioの順で絞る。
8. FDE等の外部repoからは概念と公開契約だけを参照し、コードまたは文章を複製しない。

## Execution authority

```text
parameter registry
→ agent observation
→ provider proposal
→ schema/resource/compatibility validation
→ deterministic arbiter
→ deterministic transition core
→ three-phase trace and six-axis check
→ next-round replan
```

単一writerはtransition coreである。renderer、Web API、provider、agent rationaleはstate writerではない。

## External provider boundary

外部provider接続はMVP coreに未実装であり、後続laneへ延期する。`run_adaptive_simulation`は互換用の
`provider`引数を一時的に保持するが、`None`または組み込みproviderの正確な型以外をfail-closedで拒否する。
外部AIを導入するときは、別processのbounded JSON/HTTP adapterとして設計し、UTF-8 byte上限、schema、
version、content type、deadline、request/response hashをadapter側で確定してから、検証済みactionだけを
coreへ渡す。任意のPython object、pickle、provider自己申告metadataをcoreのtrust boundaryに持ち込まない。

Google Cloudのproject作成、IAM、Secret Manager、Cloud Run、GPU、課金、deployは別の外部操作であり、
このADRは実行許可を与えない。ローカルcontractがgreenになった後、専用deployment ADRと人間承認を要する。

## Consequences

- 外部AIなしで完全なdemoとreplayが成立する。
- 将来のGoogle Cloudまたは他providerは、別process JSON/HTTP adapterとしてsimulation coreから分離する。
- 全parameterの総当たりを避け、介入点を説明可能な範囲で探索できる。
- 外部provider特有の創発性はローカルengine完成後の評価laneとして残る。
