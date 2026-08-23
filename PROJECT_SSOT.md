---
type: project-ssot
status: active
owner: repository-maintainers
canonical_repository: nexus-ai-2045/space-civilization-choice
---

# プロジェクト正本マップ

このrepository identityを「宇宙文明の選択権」の現行PUBLIC product正本の配置先とする。
各文書のremote到達状態はGitHubのlive read-backに従う。
ローカルcheckout、作業branch、worktree、Codex Project登録は入口または作業実体であり、
repository identityや文書の役割を置き換えない。

## 正本マップ

| concern_id | concern | canonical file | projection / evidence |
|---|---|---|---|
| `product_goal` | product goal、scope、done_when | [`PROJECT_GOAL.md`](PROJECT_GOAL.md) | README、product spec、roadmap |
| `scenario` | 一枚シナリオ | [`docs/ONE_PAGER.md`](docs/ONE_PAGER.md) | READMEの要約 |
| `simulation_contract` | 状態、分岐、replay、分類schema | [`docs/SIMULATION_DESIGN.md`](docs/SIMULATION_DESIGN.md) | architecture、UI spec |
| `research_evidence` | 公開可能な事実・仮説・未知 | [`docs/RESEARCH_EVIDENCE.md`](docs/RESEARCH_EVIDENCE.md) | READMEの公式情報 |
| `decisions` | 設計判断 | [`docs/adr/README.md`](docs/adr/README.md) | 個別ADR |
| `reuse_boundary` | 既存基盤の採用境界 | [`docs/REUSE_MAP.md`](docs/REUSE_MAP.md) | upstream repositoryのreview済みrevision |
| `public_readiness` | 公開準備の証拠 | [`PUBLIC_READY.md`](PUBLIC_READY.md) | preflight結果。公開許可そのものではない |

同じconcernの説明を別文書へ再掲する場合、上表のcanonical fileへの相対linkを持つprojectionとして扱う。

## 正本ではないもの

- ローカル絶対path、clone名、worktree名、branch名
- Codexのtask名、Project登録、ブラウザタブ
- private原典、内部判断台帳、過去の候補シナリオ
- remoteの最新状態を再取得していないreceiptや画面表示
- LLM出力、生成文章、未承認のaction proposal

過去候補は削除せず、内部来歴側で`superseded`として保持する。本文をこのrepoへ複製しない。

## ローカル配置境界

ローカルcanonical path、origin、visibility、独立repoかlinked worktreeかの判定は、公開対象外の
workspace registryとGit実測で行う。このファイルはWindows上の絶対pathを公開契約にしない。

本repoが別repoの配下へ置かれる場合も、独立したGit common-dirとoriginを持ち、親repoから
exact pathでignoreされ、workspace registryでintentional nestingが宣言されていなければならない。

## 変更ルール

1. 正本を変更するPRは、projection、ADR、完了条件への影響を同時に確認する。
2. concernの追加・分割・owner変更は本ファイルとgoal checkerを同じPRで更新する。
3. private原典とPUBLIC productの境界変更は人間レビューを必須とする。
4. push、PR、merge、応募、公開設定はそれぞれ別のlive状態としてread-backする。

## 保証と限界

goal checkerは、このファイルのmetadata、必須heading、canonical fileへのlinkをfail-closedで検査する。
workspace registryはローカル配置とoriginの対応を検査する。どちらのpassも、remote CI、公開許可、
内容の正しさ、第三者権利、実装完了を保証しない。
