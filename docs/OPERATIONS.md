# GitHub公開運用

本repoのcommit、push、Pull Request、public化、公開後確認を一つの操作としてまとめない。
各段階で対象、名義、visibility、exact HEAD、外部に見える範囲を再測定する。

## 役割

| gate | 守るもの | 守らないもの |
|---|---|---|
| `ai-ratchet-gate` | trackedかつignoredの矛盾がbaselineより増えないこと | secret、権利、内容、公開許可 |
| `secret-scan` | exact HEADと取得履歴にgitleaks検出がないこと | 権利、内容、公開許可 |
| `repo-preflight` | tree、履歴、必須文書、secret候補、個人path、README契約 | 完全なsecret不在、第三者権利、remote CI、公開許可 |
| `github-cli-ops-guard` | remote owner、active `gh` login、credential username、repo解決、visibility | 差分品質、CI成功、操作承認 |
| `github-codeql-governance` | 対応言語、CodeQL状態、alertのread-only棚卸し | visibility変更、alert修正・dismiss、公開許可 |

どのgateのpassも、次の外部操作を自動承認しない。

既存基盤の正本、採用する契約、実行版と上流HEADの差、非採用範囲は
[`REUSE_MAP.md`](REUSE_MAP.md)へ集約する。正本のコードをこのrepoへ複製せず、上流更新は
drift確認と回帰検査を通してから採用する。

## 操作順序

### 1. ローカルcommit前

1. 対象差分だけをstageする。
2. `git diff --cached --check`、secret scan、個人path scan、Markdown link検査を実行する。
3. GitHubのdefault branchでは`secret-scan`、`goal-contract`、`ratchet (ubuntu-latest)`、
   `ratchet (windows-latest)`をrequired status checkにする。現在はeligible reviewerがowner本人だけなので
   approving review／CODEOWNERS reviewを必須化しない。第二reviewer追加後に別reviewで昇格する。
   workflowとcheckerを同じPRで変更できても、required contextを削除してgreen扱いにはしない。
   2026-08-24のPUBLIC read-backではruleset 0件、`main`保護なしである。PRで実check名を取得した後、
   別承認で設定し、read-backできるまでは「保護済み」と表現しない。
4. `ai-ratchet-gate`を通常モードで実行する。
5. 差分と検査結果を人間が確認してからcommitする。

### 2. branch push前

1. `repo-preflight --intent push --base-ref origin/main`を実行する。
2. `github-cli-ops-guard`の正式probeを実行する。
3. GitHubからvisibility、default branch、remote base、fast-forward可能性をread-backする。
   `PRIVATE`ならprivate-repo autonomyの適用条件を別途確認する。`PUBLIC`なら作業branchがnon-defaultで
   あることに加え、exact HEAD、commit数、変更file、Webから見える内容を提示して明示承認を得る。
4. visibility別の承認境界を満たしたことを確認する。
5. push後、remote branch SHAをread-onlyで照合する。

### 3. Pull Request前

1. `repo-preflight --intent open_pr --base-ref origin/main`を再実行する。
2. base、head、title、body、変更ファイル、CI対象を提示する。
3. PR作成後、URL、base、head SHA、本文、CI、review thread、mergeabilityを再取得する。
4. mergeは別承認とする。

### 4. public化前

1. README、LICENSE、SECURITY.md、secret scan、個人path scan、履歴、`PUBLIC_READY.md`を確認する。
2. `repo-preflight --intent publish --audience public`を実行する。
3. CodeQL governanceで実装言語と解析適格性を確認する。
4. `nexus-ai-2045/space-civilization-choice`と、実行するvisibility変更コマンドを明示する。
5. 全fileとcommit historyがWeb公開されることを説明し、repo固有の明示承認を得る。

### 5. public化後

1. GitHubからvisibility、default branch、README表示を再取得する。
2. 対応言語が導入済みなら、承認されたCodeQL setupを適用して初回解析を確認する。
3. Private vulnerability reportingの状態を確認する。
4. 公開URL、CI、security設定、残余リスクを記録する。

## 現在の実測

2026-08-24時点:

- repo: `nexus-ai-2045/space-civilization-choice`
- branch: `codex/public-ready-foundation`
- visibility: `PUBLIC`（本taskによる変更ではない。変更主体は未確認）
- GitHub Ops probe: `status=ok`
- remote owner、active login、credential usernameはrepo ownerと一致
- environment token override: なし
- GitHub Ops Core Suite: `nexus-ai-2045/github-ops-skills main@7d5c146`
- Codex adapter: 8 skill `READY`、配布後hash mismatch 0
- account map: schema pass、本repoとCore Suite repoだけを登録
- write preflight: PUBLIC repoへのpush / PR / settings変更は人間レビュー必須
- Core Suite検証: unit test 118 pass、live read-only E2Eは`READY / live_read_only_verified`
- CodeQL governance: 公開候補はPythonを含むため適格候補。live default branchの言語検出は空、Default setupは`not-configured`、解析実績なし
- ruleset 0件、`main` branch protectionなし
- Actions full-length SHA pinning、secret scanning、push protection、Private vulnerability reportingは設定済み・read-back済み
- worktree lifecycle read-only scan: anchor `9ad1a652...`で`protected`、未push4 commit、cleanup実行なし
- engineering-brain runtime: module解決不能のため設計契約のみ採用、runtime連携は保留
- external mutation: visibility変更なし。上記security／Actions設定は同日実施済み。本修正・再監査では追加mutationなし

GitHubの[setup種別ガイド](https://docs.github.com/en/code-security/concepts/code-scanning/setup-types)の
推奨どおり、まずPythonを指定したCodeQL Default setupを候補とする。Default setupで
必要な範囲を解析できない場合だけAdvanced setupを検討する。設定変更前に人間レビューを得る。
PUBLIC repoの各write前に`public-repo-readiness`、`repo-preflight`、本運用gateを適用する。
