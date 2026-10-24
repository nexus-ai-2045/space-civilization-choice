---
title: 探索的・逐次更新型の意思決定ループを採用する
type: adr
status: accepted
created: 2026-08-24
updated: 2026-08-24
owner: repository-maintainers
related:
  - ../../PROJECT_GOAL.md
  - ../SIMULATION_DESIGN.md
  - ../RESEARCH_EVIDENCE.md
---

# ADR-0005: 探索的・逐次更新型の意思決定ループを採用する

## Context

2040年の単一予測を作ると、未知の係数や価値判断を精度に見せかける危険がある。一方、全因子の
全組合せを列挙すると組合せ爆発を起こし、どの前提が選択肢喪失へ効いたか説明できなくなる。
また、2026年に一度だけ決めた経路を2040年まで固定すると、途中の観測から学べない。

## Decision

上位方法論に探索的モデリング（Exploratory Modeling and Analysis）と、深い不確実性下の
ロバスト意思決定（Robust Decision Making）を採用する。各review時点では現在状態を観測し、
残り期間の有限な分岐を再評価して、直近の一手と切替条件を人間が選ぶ。

この反復はMPCに着想を得るが、予測モデル、有限horizonの目的、制約付き反復最適化、観測更新、
最適列の先頭行動だけの適用を実装するまでMPCそのものとは呼ばず、「逐次更新型の適応計画」と
表現する。安定性はMPCの定義ではなく、別途検証する保証項目とする。

RDMのproblem framingはXLRMとして記録する。Xは外生的不確実性、Lは選択可能なpolicy lever、
Rは入力と結果を結ぶモデル内関係、Mは複数のperformance measureである。robustnessとregretは
measureごとのthresholdとensembleに対して定義し、一件の脆弱性発見だけをrobustnessの証明にしない。

組合せ爆発は次の順序で抑える。

1. 政策的意味を保った有限の因子と離散状態を定義する。
2. 整合しない組合せを根拠付きで除外する。
3. 因子スクリーニングで影響の小さい因子を予備選別する。
4. 残った因子から、脆弱性と選択肢喪失を生む条件をscenario discoveryで抽出する。
5. 除外、固定、採用した因子と根拠をmodel cardへ残す。
6. `max_runs`、seed数、sampling法、interaction test、停止条件をensemble manifestへ残す。

## Allowed

- plausible futures、脆弱性、後悔、tipping point、option valueを複数軸で比較する
- review時点で事実snapshotと未知を更新し、残りhorizonを再実行する
- 説明可能性を保つ有限領域化、因子スクリーニング、感度分析を使う
- 人間が直近の行動と切替条件を選び、run manifestへ記録する

## Prohibited

- 一つの未来を「最も正確な予測」として提示する
- 根拠のない確率分布、精密な小数、単一総合点で政策を自動決定する
- 説明性を失う圧縮だけで因子を除外する
- scenario discoveryで得た相関的条件を、因果関係の証明と表現する
- MPCの実装要件を満たさない段階で「MPCを実装済み」と表現する

## Human Review Gate

観測軸の閾値、因子の除外、価値の重み、tipping point、許容可能な後悔、政策提言への転用は
人間レビューを必須とする。シミュレーションは判断材料を作るが、政策決定を自動化しない。

## Consequences

未来予測の正しさではなく、どの条件で選択肢が失われ、どの行動が複数の将来に耐えるかを
比較できる。代わりに、XLRM、factor inventory、ensemble manifest、model card、run manifest、
performance threshold、感度分析、feedback ledgerが実装上の必須成果物になる。

## Review Evidence

- Steve Bankes, “Exploratory Modeling for Policy Analysis,” 1993
- Lempert, Popper, Bankes, *Shaping the Next One Hundred Years*, RAND, 2003
- Haasnoot et al., “Dynamic adaptive policy pathways,” 2013
- Morris, “Factorial Sampling Plans for Preliminary Computational Experiments,” 1991

URLと採用範囲は`docs/RESEARCH_EVIDENCE.md`に記録する。

## Next Actions

- Phase 1でrun manifest、model card、factor inventoryのschemaを定義する
- 同一入力replayと三分岐共通条件をtestへ固定する
- Phase 2でXLRM、run budget、factor screening、scenario discovery、holdout stabilityを小さなfixtureに適用する
