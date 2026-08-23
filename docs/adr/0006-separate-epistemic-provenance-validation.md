---
title: 知識状態・記録種別・生成元・検証状態を分離する
type: adr
status: accepted
created: 2026-08-24
updated: 2026-08-24
owner: repository-maintainers
related:
  - ../../PROJECT_GOAL.md
  - ../SIMULATION_DESIGN.md
  - ../UI_SPEC.md
  - ../SECURITY_MODEL.md
---

# ADR-0006: 知識状態・記録種別・生成元・検証状態を分離する

## Context

従来案は`fact`、`scenario_hypothesis`、`model_assumption`、`llm_proposal`、`unknown`を
一つの分類へ入れていた。しかし`llm_proposal`は内容の確からしさではなく生成元と処理段階であり、
事実や未知と同じ軸ではない。このままでは「LLM由来だから未知」「人間が受理したから事実」といった
不正な昇格をschemaで防げない。

## Decision

schema contractは`epistemic-provenance-validation/v1`とする。

event、claim、action proposalを次の四つの直交fieldで記録する。

| field | 許可値 | 答える問い |
|---|---|---|
| `record_kind` | `source_claim` / `exogenous_event` / `simulated_transition` / `action_proposal` | 何を記録しているか |
| `epistemic_class` | `fact` / `scenario_hypothesis` / `model_assumption` / `inference` / `unknown` | 内容をどの知識状態として扱うか |
| `provenance_type` | `official_source` / `human_input` / `deterministic_core` / `llm` | どこから来たか |
| `validation_state` | `proposed` / `accepted_for_run` / `rejected` / `superseded` | runへ採用できる状態か |

LLM出力は`provenance_type=llm`に固定するが、それだけで`epistemic_class`を決めない。
決定論的コアの出力も実世界の事実へ昇格せず、`record_kind=simulated_transition`として保持する。
`accepted_for_run`はモデル入力としての採用であり、現実世界で真であることの承認ではない。

## Allowed

- 同じclaimへ四fieldとsource ID、reviewer、review時刻を付ける
- UIで四軸を別label、filter、形状として表示する
- 互換性のない組合せをschemaとnegative testで拒否する
- enum追加が必要な場合、model versionとmigrationを伴うADRで見直す

## Prohibited

- 生成元だけで内容の真偽を決める
- `accepted_for_run`をfact verificationまたは政策承認と表現する
- LLMの文章を決定論的状態遷移の正本にする
- 四軸を表示用の単一badgeへ不可逆に圧縮する

## Human Review Gate

許可値、互換性規則、factへの昇格条件、LLM提案の採否、既存runのmigrationは人間レビューを必須とする。
schema検査のpassは、claimの内容またはrunの政策的妥当性を承認しない。

## Consequences

知識の確からしさ、生成元、記録対象、採否を別々に検索・検査できる。一方、event schemaとUIは
field数が増えるため、Phase 1でJSON Schema、互換性matrix、negative fixtureを先に作る必要がある。

## Review Evidence

- [`ADR-0002`](0002-hybrid-deterministic-llm-simulation.md): LLMと決定論的コアの責務分離
- [`SECURITY_MODEL.md`](../SECURITY_MODEL.md): 未信頼入力と状態変更権限の境界

## Next Actions

- Phase 1で四fieldを必須にしたevent JSON Schemaを作る
- 代表的な正例と、LLM由来fact自動昇格などの負例をfixture化する
- UIで四軸を色だけに依存せず表示する
