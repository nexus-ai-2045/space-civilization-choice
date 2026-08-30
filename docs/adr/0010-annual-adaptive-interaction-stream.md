# ADR-0010: 適応型Webだけを年次化し、実計算progressをstreamする

- Status: accepted
- Date: 2026-08-30
- Extends: ADR-0009

## Context

固定比較fixtureと`meta-security-run-bundle/v1`は、2026 / 2030 / 2035 / 2040の4時点を
比較・検証する正本契約である。一方、ハッカソンの操作体験では、2026年から2040年まで毎年、
主体同士の応答と再計画が進むことを観測できる必要がある。4時点の定数を直接15年へ変更すると、
比較fixture、event順序、既存bundleの再現性を破壊する。

また、全計算後の結果を時間差表示するだけでは、実計算progressと誤認される。

## Decision

1. 固定比較の`simulation.ROUNDS`と`meta-security-run-bundle/v1`は変更しない。
2. 適応型Webだけが`ADAPTIVE_YEARS = 2026..2040`の15年次を持つ。
3. 各年は初期提案、他主体への応答、再提案、資源調停、単一writerによる状態更新の順とする。
4. 相互作用記録は状態遷移用`execution_records`へ混ぜず、専用recordとcanonical hashを持つ。
5. 行動効果と不確実性はcarry付き固定小数点で年次配分し、従来4回相当のスケールを維持する。
6. `POST /api/simulate/stream`はNDJSONで実計算eventを送る。時刻や接続状態はcanonical resultへ入れない。
7. 完了後の年次アニメーションは結果リプレイと明記し、live計算として表示しない。
8. 外部AI、Cloud Run、公開、releaseの権限はこのADRでは付与しない。

## Invariants and detectors

- 固定比較テストで4時点とrun bundleのstrict verifyを維持する。
- 適応型テストで15年の連続順序、各年5主体、自己応答禁止、同seed同hashを検査する。
- 15回のfull effect適用を禁止し、早期0/100飽和とcarry reconciliationを検査する。
- UIは受信したstream eventだけを計算progressとして表示し、完了後はリプレイ表示へ切り替える。

## Consequences

- 固定比較の再現性を壊さず、年ごとの主体間相互作用を操作・観測できる。
- 新規runtime dependencyは不要で、Python coreと既存Phaser UIを維持する。
- 外部providerを採用する場合も、検証済みproposalだけを渡す別process境界が必要である。
