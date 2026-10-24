# ADR-0003: Python coreとReact + Vite UIを分離する

- 状態: proposed
- 日付: 2026-08-24

## 文脈

政策simulationは、検証しやすい計算コアと、因果・分岐を探索するUIの両方が必要である。
現時点で実装はなく、技術選定は検証されていない。

## 決定

Pythonをsimulation coreの第一候補、React + Viteを比較UIの第一候補とし、JSON schemaと
event logで境界を作る。API keyはbrowserへ置かない。最初の実装はCLI fixtureから始め、
UIより先にreplay testを通す。

## 結果

計算と表示を独立に検証できるが、二つのruntimeとschema互換性を管理する必要がある。
まだコードを導入していないため状態を`proposed`とする。

## 見直し条件

Phase 1のspikeでpackage複雑性、性能、配布方法がMVPに合わないと判明したとき。
