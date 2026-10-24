---
title: 外部基盤の採用レベルと運用証拠を分離する
type: adr
status: accepted
created: 2026-08-25
updated: 2026-08-25
owner: repository-maintainers
related:
  - ../../PROJECT_GOAL.md
  - ../../PROJECT_SSOT.md
  - ../REUSE_MAP.md
  - ../OPERATIONS.md
  - ../../ops/adoption-manifest.json
---

# ADR-0007: 外部基盤の採用レベルと運用証拠を分離する

## Context

既存基盤を一覧へ載せただけでは、設計を参考にした状態と、CIで毎回拒否できる状態が同じ
「採用」に見える。さらに上流default HEAD、実行したrelease、ローカルadapterが混ざると、
何が保証され、何が未接続なのかを再現できない。非公開の内部基盤をPUBLIC productの依存として
暗黙に公開することも避ける必要がある。

## Decision

正本契約を`space-civilization-operational-adoption/v1`とし、採用状態を次の五段階へ固定する。

| level | 意味 | 必須証拠 |
|---|---|---|
| `enforced_ci` | required CI context内で自動拒否できる | 固定releaseとhash、workflow、baseline |
| `operator_gate` | 外部操作ごとに人が起動するfail-closed gate | 実行版、intent、receipt、write後read-back |
| `design_reference` | 原則または設計契約だけを採用 | review済みrevisionとrepo内の接続先 |
| `future_candidate` | 導入条件が未成立 | 再評価条件。接続先は持たない |
| `out_of_scope` | 現行product boundary外 | 境界理由。接続先は持たない |

この分類と証拠の正本は[`ops/adoption-manifest.json`](../../ops/adoption-manifest.json)とする。
checkerを既存required `goal-contract` jobで実行し、分類の過大表示、固定hashとの不一致、
証拠path欠落、非公開entryへのrepository URLまたはrevision記録を拒否する。

公開基盤の上流default HEADは依存lockではない。`enforced_ci`はrelease artifactとSHA-256を固定し、
`operator_gate`と`design_reference`はreview済みrevisionを記録する。upstream driftは通知対象だが、
自動upgradeしない。非公開基盤からは一般化した契約だけを採り、名前、URL、revision、本文は
PUBLIC treeへ収録しない。

## Allowed

- 公開sourceのURL、review済みrevision、release、artifact hashをmanifestへ記録する
- 非公開sourceから一般化した境界、成熟度、fan-in、証拠台帳の契約だけを採用する
- driftを検出し、人間レビュー後にrevisionまたはreleaseを更新する
- `operator_gate`のreceiptとread-backを操作単位で保存する

## Prohibited

- `design_reference`または`future_candidate`を運用保証済みと表現する
- gateのpassをpush、PR、merge、release、公開の承認へ昇格する
- 非公開sourceの名前、URL、revision、本文をPUBLIC product依存として暗黙に公開する
- 上流default HEADへ追随するだけの自動更新
- 音声対話、記事公開、常駐process guardを現行Web MVPへ無条件で接続する

## Human Review Gate

採用levelの昇格、releaseまたはreview済みrevisionの更新、baseline変更、新規runtime依存、
公開sourceの追加、非公開contractの公開表現変更は人間レビューを必須とする。
checkerのpassは外部writeや公開の承認ではない。

## Consequences

「使える」と「毎回保証される」を分離でき、車輪の再発明を避けながら保証範囲を過大表示しない。
一方、operator gateは自動CIだけでは完結せず、外部操作ごとのreceiptとread-backが必要になる。

## Review Evidence

- [`REUSE_MAP.md`](../REUSE_MAP.md): 公開基盤ごとの採用levelと接続先
- [`OPERATIONS.md`](../OPERATIONS.md): 外部操作前後のgate順序
- [`adoption-manifest.json`](../../ops/adoption-manifest.json): 機械可読な正本
- [`check_operational_adoption.py`](../../scripts/check_operational_adoption.py): 過大表示を拒否する検査

## Next Actions

- Phase 1でruntime依存が生じた時だけ、package lock、license、security、撤去方法を追加審査する
- 外部writeごとにoperator gateの実行版とreceiptを更新する
- upstream driftは別PRで評価し、同時に複数基盤を暗黙更新しない
