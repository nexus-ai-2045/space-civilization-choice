# Design QA: Causal Constellation

- source visual truth: external QA artifact `generated_images/.../causal-constellation-concept.png`（repo保存版: `docs/design/causal-constellation-concept.png`）
- implementation screenshot: external QA artifact `visualizations/.../constellation-desktop.png`
- combined comparison: external QA artifact `visualizations/.../constellation-comparison.png`
- viewport: desktop 1440 x 1024 CSS px、device scale factor 1相当
- source pixels: 1488 x 1058
- implementation pixels: 1440 x 1024
- density normalization: sourceを高さ1024へ等比縮小し、実装と横並びにして比較
- state: balanced初期値をlocal deterministic providerで4ラウンド実行後

## Findings

P0 / P1 / P2の未解決差分はない。

- フォントと文字組み: 日本語system UI fontで小さいラベルも判読可能。見出し階層と英字タイトルの字間はsourceの意図を維持している。
- 余白とレイアウト: 左の20入力、中央の因果盤、右のtraceという三分割を維持。実装は入力数増加に合わせて左ペインをスクロール化した意図的差分。
- 色とtoken: 深紺背景、認知の紫、組織の青、能力の黄、主体の補助色がsourceと整合する。
- 画像品質: sourceの装飾を画像代替せず、実データに追随するPhaser canvasとして再構成した。円・線・文字は高密度表示でも鮮明。
- copy/content: `deterministic_local_v1`、4ラウンド、六軸、提案採否を実APIの値として表示する。mock fallbackは削除済み。

P3 polish:

- sourceにある選択経路の強い発光とagent説明は、実装では密度を抑えた静的リンクと短縮名になっている。ゲーム演出の次段階で強化できる。
- Phaser本体の初期bundleが約1.49 MB。機能を損なわない遅延ロードは後続最適化候補。

## Full-view comparison evidence

同一高さへ正規化したcombined comparisonで、情報アーキテクチャ、三領域の位置、左右の操作・証拠ペイン、timeline、paletteを確認した。

## Focused region comparison evidence

中央因果盤、左parameter controls、右proposal/axesを原寸画像で確認した。sourceと実装はいずれもdesktop全体でラベルを読めるため、追加cropは不要だった。

## Responsive evidence

- mobile capture: external QA artifact `visualizations/.../constellation-mobile-v3.png`
- Edge headlessの最小layout viewportが指定390pxより広く、390px画像へcropされるため、これは厳密な390 CSS px fidelity比較には用いていない。
- responsive CSSでは中央盤を先頭にし、横overflowを閉じ、操作・証拠ペインを縦積みにする契約を確認した。

## Runtime checks

- browser-rendered desktop screenshot: captured
- primary interaction: POST `/api/simulate`、20 parameter変更、4 round完走、hash変化を確認
- failure interaction: unknown top-level fieldがHTTP 400でfail closed
- console errors: Edge headlessのconsole収集APIが利用できず未収集。HTTP/API/buildエラーはなし
- build: `npm run build` passed

## Comparison history

1. 初回captureはserver停止中の接続拒否画面でblocked。正しいlocal serverを再起動した。
2. 実装captureで英語action IDとmobile横overflow候補を確認。action labelを日本語化し、responsive overflow contractを追加した。
3. 再build、実API smoke、desktop captureを実施。P0 / P1 / P2なし。

final result: passed
