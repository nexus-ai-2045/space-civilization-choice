# 既存基盤の再利用マップ

このrepoは、判断制御、開発保証、GitHub操作、worktree管理、公開前検査、回帰防止を
独自実装しない。それぞれの正本を分離したまま、必要な契約とgateだけを利用する。

記録日: 2026-08-24

## 採用マップ

| 正本 | このrepoで採用する契約 | 利用形態 | 参照したdefault HEAD |
|---|---|---|---|
| [Fractal Decision Ecosystem](https://github.com/nexus-ai-2045/fractal-decision-ecosystem) | Goal → Evidence → Decision → Verify → Closure、事実・推測・不明の分離、公開停止線 | 設計契約 | [`a41aff6`](https://github.com/nexus-ai-2045/fractal-decision-ecosystem/commit/a41aff6b0e4eefe728d6177017212b89be7820e2) |
| [engineering-brain](https://github.com/nexus-ai-2045/engineering-brain) | reuse-first、実装・検証・運用保証・人間判断の分離 | 設計契約。runtimeは下記理由で保留 | [`b7428b4`](https://github.com/nexus-ai-2045/engineering-brain/commit/b7428b4ddc4b75f7e091e1e1bc50473e58b12d9f) |
| [github-ops-skills](https://github.com/nexus-ai-2045/github-ops-skills) | remote、identity、visibility、承認境界、write後read-back | 実行gate | [`05d7762`](https://github.com/nexus-ai-2045/github-ops-skills/commit/05d7762c32c2ee3975d6fb2f4b6e2e2a4827f210) |
| [worktree-lifecycle-control](https://github.com/nexus-ai-2045/worktree-lifecycle-control) | worktreeを削除対象ではなく、統合証跡を持つ作業資産として扱う | read-only scan | [`dd27137`](https://github.com/nexus-ai-2045/worktree-lifecycle-control/commit/dd27137d2130539a9b5687622e254de8cb0eeac0) |
| [repo-preflight](https://github.com/nexus-ai-2045/repo-preflight) | secret、個人path、履歴、必須文書、README、公開境界のfail-closed検査 | 実行gate | [`b63a0af`](https://github.com/nexus-ai-2045/repo-preflight/commit/b63a0afbda4eaa1ca7970355c41bf6fd73a52a32) |
| [ai-ratchet-gate](https://github.com/nexus-ai-2045/ai-ratchet-gate) | 既存baselineを急に全修復せず、新しい悪化だけを止める | 実行gate | [`627049c`](https://github.com/nexus-ai-2045/ai-ratchet-gate/commit/627049cff78a671379159a9bf3057b22ed304dc7) |

default HEADは参照時点の上流状態であり、このrepoの依存lockではない。実行に使うローカル版と
上流HEADに差がある場合、暗黙に更新せず、検証結果へ実行版を記録する。

## このrepoへの接続

| 契約 | repo内の接続先 | 現在の証拠 |
|---|---|---|
| FDEのgoalとfeedback | [`PROJECT_GOAL.md`](../PROJECT_GOAL.md)、[`ADR-0005`](adr/0005-adaptive-exploratory-decision-loop.md) | ゴール、未知、完了条件、最小PDCA、return pathを分離 |
| engineering-brainの開発保証 | [`ROADMAP.md`](ROADMAP.md)、[`OPERATIONS.md`](OPERATIONS.md) | phase別done_whenと、local／remote／人間判断を分離 |
| GitHub Ops | [`OPERATIONS.md`](OPERATIONS.md)、[`PUBLIC_READY.md`](../PUBLIC_READY.md) | identity probeとsettings read-backを記録 |
| worktree lifecycle | 本文書とGitの作業branch | read-only scanで`protected`、`unpushed_commits=3`、変更なしを確認 |
| repo preflight | [`PREFLIGHT.md`](../PREFLIGHT.md)、CI | README設計、リンク、履歴、公開intentを検査 |
| ratchet | [`.ai-ratchet-gate/baseline.txt`](../.ai-ratchet-gate/baseline.txt)、CI | baseline 0、新規矛盾0を維持 |

## 既知の差分と停止線

- `engineering-brain`のローカルCLIは2026-08-24の確認でPython moduleを解決できなかった。
  このrepoのために別実装を作らず、runtime連携は正本の復旧とversion確認まで保留する。
- `github-ops-skills`は検査時のローカル版と現在の上流HEADが異なる。既存の検査証跡は
  実際に使った版を正とし、上流更新は別のdrift確認を通す。
- `worktree-lifecycle-control`のscanはcleanup許可ではない。branch、worktree、commitの削除は行わない。
- どのgateのpassも、PUBLIC repoへのpush、Pull Request、merge、releaseを承認しない。

## 権利と依存境界

このrepoへ上記6リポのコード、画像、文書本文は複製していない。URL、commit ID、契約の要約だけを
記録する。将来コードをvendor、fork、package依存として導入する場合は、対象commitのlicense、
security、更新方法、撤去方法を再確認し、ADRと人間レビューを追加する。
