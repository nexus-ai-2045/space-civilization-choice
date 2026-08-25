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
採用level、固定版、証拠path、drift方針の機械可読な正本は
[`adoption-manifest.json`](../ops/adoption-manifest.json)とし、既存required `goal-contract`で
[`check_operational_adoption.py`](../scripts/check_operational_adoption.py)を実行する。

## 操作順序

### 1. ローカルcommit前

1. 対象差分だけをstageする。
2. `git diff --cached --check`、secret scan、個人path scan、Markdown link検査を実行する。
3. GitHubのdefault branchでは`secret-scan`、`goal-contract`、`ratchet (ubuntu-latest)`、
   `ratchet (windows-latest)`をrequired status checkにする。現在はeligible reviewerがowner本人だけなので
   approving review／CODEOWNERS reviewを必須化しない。第二reviewer追加後に別reviewで昇格する。
   workflowとcheckerを同じPRで変更できても、required contextを削除してgreen扱いにはしない。
   2026-08-25のPUBLIC read-backではactive main ruleset `21258820`があり、上記4 contextを
   GitHub Actions app ID `15368`へ固定している。workflow内のjob名変更はruleset変更として扱う。
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

2026-08-25時点:

- repo: `nexus-ai-2045/space-civilization-choice`
- remote main: `290d511b03329a89c9e1c78832a08578ed8b67d8`
- visibility: `PUBLIC`
- main CI: run `32686326484`でrequired 4 context成功
- active main ruleset: `21258820`
- required checks: `secret-scan`、`goal-contract`、`ratchet (ubuntu-latest)`、`ratchet (windows-latest)`
- force pushとbranch deletion: 禁止
- GitHub Ops probe: `status=ok`
- remote owner、active login、credential usernameはrepo ownerと一致
- environment token override: なし
- GitHub Ops: `operator_gate`。review済み上流revisionはmanifestへ記録し、外部writeごとに実行版をreceiptへ残す
- repo-preflight: `operator_gate`。intentごとに再実行する
- worktree lifecycle: `operator_gate`。read-only棚卸しでありcleanup権限ではない
- ai-ratchet-gate: `enforced_ci`。release `v0.1.1`とwheel SHA-256をworkflow固定
- FDEとengineering-brain: `design_reference`。runtime保証ではない
- write preflight: PUBLIC repoへのpush / PR / settings変更は人間レビュー必須
- external mutation: 本運用契約の作成時点ではpush、PR、merge、settings変更なし

GitHubの[setup種別ガイド](https://docs.github.com/en/code-security/concepts/code-scanning/setup-types)の
推奨どおり、まずPythonを指定したCodeQL Default setupを候補とする。Default setupで
必要な範囲を解析できない場合だけAdvanced setupを検討する。設定変更前に人間レビューを得る。
PUBLIC repoの各write前に`repo-preflight`、GitHub Ops、本運用gateを適用する。
