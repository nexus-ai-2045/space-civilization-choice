# コントリビューション

## 変更原則

- 事実、シナリオ仮説、未知を分ける
- 現在の制度・組織については公式一次資料を優先する
- 実在する組織や人物の意図を、根拠なくシミュレーション設定へ混ぜない
- 第三者資料本体、非公開情報、個人情報をcommitしない
- `main`へ直接pushせず、branchとPull Requestを使う

## commit前

```powershell
$ratchet = Join-Path $env:APPDATA 'Python\Python313\Scripts\ai-ratchet-gate.exe'
& $ratchet --repo .
```

gate通過は、秘密情報、権利、内容品質、公開可否を保証しません。

## GitHub操作前

maintainerは、PR、push、公開操作の直前に次の順でgateを実行します。

1. `ai-ratchet-gate`でtrackedかつignoredの増加を止める
2. `repo-preflight`を対象intentで実行する
3. `github-cli-ops-guard`でremote owner、active login、credential username、visibilityを照合する
4. external write後にremote branch、PR、CIをread-onlyで再取得する

ローカルskillの絶対pathは環境ごとに異なるため、本repoへ固定しません。詳細は
[`docs/OPERATIONS.md`](docs/OPERATIONS.md)を参照してください。
