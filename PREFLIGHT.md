<!-- repo-preflight:review-record -->

# 公開変更のpreflight記録

- base: `origin/main@290d511b03329a89c9e1c78832a08578ed8b67d8`
- 対象: 運用採用manifest、ADR-0007、checker、CI接続、運用文書の現状同期
- 確認日時: `2026-08-25`
- 判定: `local_validation_in_progress`
- external mutation: なし

## baseで確認済み

- [x] repositoryは`PUBLIC`、default branchは`main`
- [x] main exact HEADは`290d511b03329a89c9e1c78832a08578ed8b67d8`
- [x] main CI run `32686326484`でrequired 4 context成功
- [x] active main ruleset `21258820`とrequired contextをread-back
- [x] 公開基盤と非公開内部基盤を分離し、非公開source identityは公開成果物へ入れない
- [x] 独立worktreeとnon-default branchで作業

## この変更で検証するもの

- [x] unit test 40件とproject goal checker
- [x] operational adoption checker `operational_contract_valid`
- [x] workflow設定検査とPython compile
- [x] ai-ratchet-gate 既存0件／新規0件
- [x] target diffのsecret候補0件、個人path 0件
- [ ] commit後の履歴とMarkdown linkを再検査
- [ ] `repo-preflight --intent open_pr --base-ref origin/main`
- [ ] final exact diffの人間レビュー
- [ ] branch push後のexact HEAD CI、review thread、mergeability

## 人間目視

- reviewer: 未実施
- reviewed_at: 未実施
- exact HEAD / PR diff: 未commit・未push
- decision: `review_pending`
- 外から見える内容: branchをpushすると、採用level、公開基盤のURLとreview済みrevision、
  ADR-0007、checker、テスト、更新した運用文書がWebから閲覧可能になる
- 公開除外: 非公開sourceの名前、URL、revision、本文、個人log、応募情報
- 残余リスク: 上流drift、operator gateの実行漏れ、設計参照をruntime保証と誤読すること
- 次の停止線: final exact diffと全検査結果を提示し、PUBLIC branch push／PRの明示承認を得る
