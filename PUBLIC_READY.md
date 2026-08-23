# 公開準備記録

状態: **PUBLIC／mainは初期commitのみ／公開設計branchは未push**

このファイルは公開判断の証拠を集めるものであり、公開許可そのものではありません。

## 対象

- GitHub repository: `nexus-ai-2045/space-civilization-choice`
- default branch: `main`
- 作業branch: `codex/public-ready-foundation`
- 公開候補: README、LICENSE、SECURITY.md、CONTRIBUTING.md、設計文書、ADR、gate設定
- 公開除外: 応募者のメールアドレス、フォーム回答、参加者番号、内部資料、内部要約、非公開log

## 2026-08-24のローカル実測

- [x] GitHub APIと`git ls-remote`でvisibility=`PUBLIC`、default branch=`main`をread-back
- [x] Web公開中の`main`は初期commit `5cd937a`のみで、公開設計commitは未push
- [x] 本taskはvisibility変更を実行していない。変更主体は未確認として扱う
- [x] MIT LICENSEあり
- [x] README、SECURITY.md、CONTRIBUTING.md、PREFLIGHT.mdあり
- [x] 第三者文書本体を収録せず、公式公開URLと必要最小限の要約のみ利用
- [x] `ai-ratchet-gate` baselineは矛盾0件で固定
- [x] trackedかつignoredの矛盾0件
- [x] gitleaks working tree 0件
- [x] gitleaks既存履歴 0件（既存1commitを検査）
- [x] staged personal path・応募メール・参加者番号 0件
- [x] ゴール契約の必須Markdown linkとrepo内target検査pass
- [x] GitHub Actions YAML parse pass
- [x] `git diff HEAD --check` pass
- [x] ゴール契約mutation test 8件pass
- [x] ゴール契約checker v2は`contract_valid_product_incomplete`（契約有効、MVP未完成）
- [x] `secret-scan`、`goal-contract`、2 OSの`ratchet`をexact HEADで実行するCI定義あり
- [x] ハッカソン、片山さんコンセプトペーパー、JAXA、内閣府の公式URL到達確認
- [x] GitHub接続名義は`nexus-ai-2045`、repo ownerと一致
- [x] commit作者名は`nexus_ai`、メールはGitHub noreply domain
- [x] 既存初期commitのcommitterはGitHub標準`GitHub <noreply@github.com>`で、個人メールではない
- [x] `github-cli-ops-guard`正式probe `status=ok`
- [x] remote owner、active `gh` login、credential usernameはすべて`nexus-ai-2045`
- [x] `GITHUB_TOKEN` / `GH_TOKEN`によるaccount上書きなし
- [x] [github-ops-skills](https://github.com/nexus-ai-2045/github-ops-skills) `main@7d5c146`を正本としてCodex向け8 skillをhash照合
- [x] local account mapへ本repoを登録し、`github-ops/account-map/v1` schema検証pass
- [x] 最新identity probeは`READY / identity_verified`
- [x] PUBLIC repoへのpush／PR／settings変更は、PRIVATE時の自動許可を無効として人間レビューへ停止
- [x] CodeQL governance read-only監査: 現在はdocs-only・主言語なしのため`unsupported`
- [x] ruleset 0件、`main` branch protectionなしをlive APIで確認
- [x] Actionsは有効、allowed actionsは`all`、full-length SHA pinning必須化をread-back
- [x] secret scanningとpush protectionの有効化をread-back
- [x] Private vulnerability reportingの有効化をread-back
- [x] Dependabot security updatesは未設定（現在は依存manifestなし）
- [x] 既存6基盤はURL、commit ID、契約要約だけを参照し、コード・画像・文書本文の複製なし
- [ ] 公開候補commit作成後の全履歴gitleaks再検査
- [ ] exact HEADのremote CI pass
- [ ] exact diffの人間レビュー
- [ ] PRの実check名を取得後、required checksとforce-push／delete防止rulesetを設定・read-back
- [x] Actions SHA pinning、secret scanning、push protectionを設定・read-back
- [x] GitHubのPrivate vulnerability reporting設定をPUBLIC状態でread-back
- [ ] 公開後のREADME、リンク、visibilityのread-back

## 検査の限界

機械検査は独自形式の秘密、画像・大容量binary、第三者素材の権利、内容の妥当性、remote設定、
実際のCI成功を完全には保証しません。Malwarebytesのrepo URL検査は`unknown`で、GitHub domainが
広く利用されていること以上の安全保証には使っていません。

`github-cli-ops-guard`のpassは名義と対象の一致を示すだけで、push、PR、公開の承認ではありません。
CodeQLの`unsupported`は安全性の合格ではなく、現時点で解析対象の実装言語がないという分類です。
github-ops-skillsのunit test、Codex adapter検証、対象repoを固定したlive read-only E2Eがpassし、
L3 read-only実行保証は`READY / live_read_only_verified`です。外部writeの成功や承認は意味しません。

## 追加公開の停止線

このrepoは既にPUBLICである。branch push、PR、merge、settings変更により新しくWebへ見える内容を、
対象repo、exact HEAD、README、LICENSE、SECURITY.md、secret scan、personal path scanと共に提示する。
repo固有の明示承認を得るまで、公開branchへのpush、merge、settings変更を行わない。
