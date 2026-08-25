# 公開準備記録

状態: **PUBLIC main稼働中／運用採用契約の変更はローカル人間レビュー待ち**

このファイルは公開判断の証拠を集めるものであり、push、PR、merge、releaseの許可ではありません。

## 対象

- GitHub repository: `nexus-ai-2045/space-civilization-choice`
- default branch: `main`
- public main: `290d511b03329a89c9e1c78832a08578ed8b67d8`
- local branch: `codex/operational-adoption-contract`
- 変更候補: 採用manifest、ADR-0007、checker、テスト、CI接続、運用文書
- 公開除外: 応募者情報、内部資料、非公開source identity、個人log、内部task状態

## 2026-08-25のlive read-back

- [x] visibility=`PUBLIC`、default branch=`main`
- [x] main exact HEAD=`290d511b03329a89c9e1c78832a08578ed8b67d8`
- [x] main CI run `32686326484`のrequired 4 context成功
- [x] active main ruleset `21258820`
- [x] required checksをGitHub Actions app ID `15368`へ固定
- [x] force pushとbranch deletionを禁止
- [x] README、LICENSE、SECURITY.md、CONTRIBUTING.mdあり
- [x] `ai-ratchet-gate` release `v0.1.1`とwheel SHA-256をworkflow固定
- [x] 公開基盤はURLとreview済みrevisionだけを参照し、コード・画像・文書本文を複製しない
- [x] 非公開基盤は一般化した契約だけを採り、repository URLとrevisionをmanifestへ収録しない
- [x] FDEとengineering-brainは`design_reference`でありruntime保証ではない
- [x] GitHub Ops、worktree lifecycle、repo-preflightは`operator_gate`であり常時CI保証ではない
- [x] Note記事公開と音声対話runtimeは現行simulation productの境界外
- [x] 変更後のunit test 40件、goal checker、adoption checker、compile、ratchet成功
- [x] target diffのsecret候補0件、個人path 0件
- [ ] final exact HEADの履歴、link、preflight検査
- [ ] exact diffの人間レビュー
- [ ] 明示承認後にPUBLIC branch pushとPR作成
- [ ] push後のexact HEAD CI、review thread、mergeability回収

## 検査の限界

採用manifestとcheckerは、採用level、固定値、証拠path、非公開source境界の内部整合を検査する。
上流sourceの内容の正しさ、未知のsecret、第三者権利、政策的妥当性、operator gateの将来の実行、
外部writeの承認までは保証しない。

## 追加公開の停止線

このrepoは既にPUBLICである。branch pushにより新しくWebへ見えるexact diff、README、LICENSE、
SECURITY.md、secret scan、personal path scan、全検査結果を提示し、repo固有の明示承認を得るまで
push、PR、merge、settings変更を行わない。
