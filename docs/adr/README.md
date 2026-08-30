# Architecture Decision Records

ADRは、設計上の重要判断と、採らなかった選択肢、見直し条件を残す。

- [ADR-0001: 2026年の現実を起点にする](0001-reality-first-simulation-horizon.md)
- [ADR-0002: 決定論的コアと限定LLMを分離する](0002-hybrid-deterministic-llm-simulation.md)
- [ADR-0003: Python coreとReact + Vite UIを分離する](0003-web-product-boundary.md)
- [ADR-0004: 公開repoと内部資料を分離する](0004-public-repository-boundary.md)
- [ADR-0005: 探索的・逐次更新型の意思決定ループを採用する](0005-adaptive-exploratory-decision-loop.md)
- [ADR-0006: 知識状態・記録種別・生成元・検証状態を分離する](0006-separate-epistemic-provenance-validation.md)
- [ADR-0007: 外部基盤の採用レベルと運用証拠を分離する](0007-operational-adoption-contract.md)
- [ADR-0008: ハッカソン向け限定AIデモを前倒しする](0008-hackathon-ai-demo-slice.md)
- [ADR-0009: ローカル優先の適応型シミュレーションエンジンを正本にする](0009-local-first-adaptive-simulation-engine.md)
- [ADR-0010: 適応型Webだけを年次化し、実計算progressをstreamする](0010-annual-adaptive-interaction-stream.md)

状態は`proposed`、`accepted`、`superseded`、`rejected`を使う。重要なモデル境界を変更する場合は、
既存ADRを書き換えず、新しいADRで置き換える。
