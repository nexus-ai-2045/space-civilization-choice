# ADR-0008: ハッカソン向け限定AIデモを前倒しする

- Status: Accepted for demo slice
- Date: 2026-08-29

## Context

既存ロードマップはLLM接続をPhase 4としていたが、ハッカソンでは「AIが実際に選択へ関与するシミュレーター」を今日中に再現可能な形で示す必要がある。

## Decision

単一AI助言役をハッカソン用vertical sliceに限って前倒しする。AIは許可済みactionを厳格JSON Schemaで提案するだけで、状態を直接変更しない。決定論コアが入力検証、遷移、hash、traceを唯一の実行権威として保持する。API key欠落、timeout、不正応答では同じ入力から同じ許可済みactionを選ぶfallbackで三分岐を完走する。

## Boundary

これは公開deploy、完成版MVP、multi-agent社会シミュレーションを意味しない。API keyはブラウザへ渡さず、ローカルserver環境だけで扱う。外部公開、merge、repository settings、課金判断は人間review境界に残す。

## Consequences

デモはAI接続の有無にかかわらず再現可能になる。一方、AI提案の品質評価、model card、感度分析、人間評価は後続ゲートとして残る。
