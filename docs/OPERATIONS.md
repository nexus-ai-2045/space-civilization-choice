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

## 操作順序

### 1. ローカルcommit前

1. 対象差分だけをstageする。
2. `git diff --cached --check`、secret scan、個人path scan、Markdown link検査を実行する。
3. GitHubのdefault branchでは`secret-scan`、`goal-contract`、`ratchet (ubuntu-latest)`、
   `ratchet (windows-latest)`をrequired status checkにし、CODEOWNERS reviewを必須化する。
   workflowとcheckerを同じPRで変更できても、required contextを削除してgreen扱いにはしない。
   現在のPRIVATE repoではGitHub APIが403を返し利用できないため、public化後に別承認で設定し、
   read-backできるまでは「保護済み」と表現しない。
4. `ai-ratchet-gate`を通常モードで実行する。
5. 差分と検査結果を人間が確認してからcommitする。

### 2. branch push前

1. `repo-preflight --intent push --base-ref origin/main`を実行する。
2. `github-cli-ops-guard`の正式probeを実行する。
3. GitHubからrepoが`PRIVATE`、作業branchがnon-default、remoteがfast-forward可能であることを確認する。
4. exact HEAD、push先、公開範囲を提示して承認境界を満たす。
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
- visibility: `PRIVATE`
- GitHub Ops probe: `status=ok`
- remote owner、active login、credential usernameはrepo ownerと一致
- environment token override: なし
- GitHub Ops Core Suite: `nexus-ai-2045/github-ops-skills main@7d5c146`
- Codex adapter: 8 skill `READY`、配布後hash mismatch 0
- account map: schema pass、本repoとCore Suite repoだけを登録
- write preflight: push / PR / visibilityはいずれも承認参照なしで`BLOCKED`
- Core Suite検証: unit test 118 pass、live read-only E2Eは`READY / live_read_only_verified`
- CodeQL governance: docs-only・主言語なしのため`unsupported`
- external mutation: なし

実装言語が追加された時点でCodeQL適格性を再監査する。repoがpublicになった後でのみ
`public-repo-readiness`を適用し、privateの間は`repo-preflight`と本運用gateを使う。
