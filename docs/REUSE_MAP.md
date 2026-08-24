# 既存基盤の再利用マップ

このrepoは、既存基盤を一律に「導入済み」と表現しない。採用level、固定版、証拠、drift方針の
機械可読な正本は[`adoption-manifest.json`](../ops/adoption-manifest.json)、判断理由は
[`ADR-0007`](adr/0007-operational-adoption-contract.md)に置く。

記録日: 2026-08-25

## 採用マップ

| 正本 | 採用level | このrepoで使う契約 | 固定・review済み対象 |
|---|---|---|---|
| [Fractal Decision Ecosystem](https://github.com/nexus-ai-2045/fractal-decision-ecosystem) | `design_reference` | Goal → Evidence → Decision → Verify → Closure、事実・仮説・未知の分離 | [`a41aff6`](https://github.com/nexus-ai-2045/fractal-decision-ecosystem/commit/a41aff6b0e4eefe728d6177017212b89be7820e2) |
| [engineering-brain](https://github.com/nexus-ai-2045/engineering-brain) | `design_reference` | reuse-first、実装・検証・運用保証・人間判断の分離 | [`cbd1f4c`](https://github.com/nexus-ai-2045/engineering-brain/commit/cbd1f4cbdd83cbc09d5cf959590219288654c160) |
| [github-ops-skills](https://github.com/nexus-ai-2045/github-ops-skills) | `operator_gate` | remote、identity、visibility、承認境界、write後read-back | [`3a6688c`](https://github.com/nexus-ai-2045/github-ops-skills/commit/3a6688c5d9d4234317947d0358127949e6b718a1) |
| [worktree-lifecycle-control](https://github.com/nexus-ai-2045/worktree-lifecycle-control) | `operator_gate` | worktreeを統合証跡のある作業資産として扱うread-only棚卸し | [`3f5f035`](https://github.com/nexus-ai-2045/worktree-lifecycle-control/commit/3f5f035a8f017503865a44a6fa57ac099d95cb12) |
| [repo-preflight](https://github.com/nexus-ai-2045/repo-preflight) | `operator_gate` | push、PR、merge、公開前のfail-closed検査 | [`35a06cc`](https://github.com/nexus-ai-2045/repo-preflight/commit/35a06cc4264423951195c54ae057d82fff360c8f) |
| [ai-ratchet-gate](https://github.com/nexus-ai-2045/ai-ratchet-gate) | `enforced_ci` | trackedかつignoredの新規矛盾をrequired CI contextで拒否 | release `v0.1.1`とwheel SHA-256をworkflowで固定 |
| [note-publishing-suite](https://github.com/nexus-ai-2045/note-publishing-suite) | `out_of_scope` | Note記事の人間承認付き公開運用 | simulation productには接続しない |

本repoでFDEはFractal Decision Ecosystemを指す。宇宙・航法分野のFault Detection and Exclusionとは
別概念であり、初出では略さずに記載する。

## 非公開基盤から採るもの

親workspace境界、taskのfan-in、capability成熟度、feedback ledgerの一般契約だけを
`design_reference`として採る。非公開sourceの名前、URL、revision、本文、個人logはPUBLIC treeへ
収録しない。複数agent討議、制約管理engine、local process preflightは`future_candidate`、
音声対話runtimeは`out_of_scope`とする。

これにより「見つけた」「接続できる」「試した」「運用保証された」を分離し、証拠なしのlevel昇格を
[`check_operational_adoption.py`](../scripts/check_operational_adoption.py)で拒否する。

## 評価候補（未採用）

| 候補 | 既存機能 | 現在の判断 | 参照HEAD |
|---|---|---|---|
| [EMA Workbench](https://github.com/quaquel/EMAworkbench) | 実験設計、並列実行、PRIM、coverage／density、feature scoring、SALib連携 | Phase 2前に小fixtureで適合性・依存規模・再現性をsmokeする。現在は依存追加・コード複製なし | [`3798b37`](https://github.com/quaquel/EMAworkbench/commit/3798b375bc4208356a74432e67040f38c6cf75a5) |

採用時は上流license、package version、lock、security、撤去方法を確認し、dependency ADRを追加する。

## このrepoへの接続

| 契約 | repo内の接続先 | 現在の保証 |
|---|---|---|
| FDEのgoalとfeedback | [`PROJECT_GOAL.md`](../PROJECT_GOAL.md)、[`ADR-0005`](adr/0005-adaptive-exploratory-decision-loop.md) | 設計契約。runtime保証ではない |
| engineering-brainの開発保証 | [`ROADMAP.md`](ROADMAP.md)、[`OPERATIONS.md`](OPERATIONS.md) | 設計契約。runtime未接続 |
| GitHub Ops | [`OPERATIONS.md`](OPERATIONS.md)、[`PUBLIC_READY.md`](../PUBLIC_READY.md) | 外部writeごとのoperator receiptが必要 |
| worktree lifecycle | [`OPERATIONS.md`](OPERATIONS.md) | read-only棚卸し。cleanup権限ではない |
| repo preflight | [`PREFLIGHT.md`](../PREFLIGHT.md)、[`OPERATIONS.md`](OPERATIONS.md) | intentごとのoperator gate。passは承認ではない |
| ratchet | [workflow](../.github/workflows/ai-ratchet-gate.yml)、[baseline](../.ai-ratchet-gate/baseline.txt) | `v0.1.1` artifactをhash固定しrequired CIで実行 |
| 採用level整合 | [manifest](../ops/adoption-manifest.json)、[checker](../scripts/check_operational_adoption.py) | 既存required `goal-contract` jobで検査 |

## 既知の停止線

- `engineering-brain`は設計参照だけで、runtimeの導入・接続・運用を保証しない。
- `github-ops-skills`、`worktree-lifecycle-control`、`repo-preflight`は人が外部操作前に実行する。
  CIが代行した、または常時保証したとは表現しない。
- upstream default HEADはlockではない。releaseまたはreview済みrevisionは人間レビューなしに更新しない。
- どのgateのpassも、PUBLIC repoへのpush、Pull Request、merge、releaseを承認しない。

## 権利と依存境界

このrepoへ参照基盤のコード、画像、文書本文は複製していない。公開URL、review済みrevision、
契約の要約だけを記録する。将来コードをvendor、fork、package依存として導入する場合は、
対象versionのlicense、security、更新方法、撤去方法を再確認し、ADRと人間レビューを追加する。
