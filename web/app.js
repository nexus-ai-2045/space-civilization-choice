const labels = {
  international_integration: "国際統合",
  domestic_autonomy: "国内自立",
  open_platform: "オープンプラットフォーム",
  access_and_operation: "アクセス・運用",
  industrial_reproduction: "産業再生産",
  rule_shaping: "ルール形成",
  knowledge_continuity: "知識継承",
  relationship_choice: "関係選択",
  public_legitimacy: "公共正当性",
};

document.querySelector("#run").addEventListener("click", async () => {
  const status = document.querySelector("#status");
  status.textContent = "AI提案と3分岐を計算中…";
  try {
    const response = await fetch("/api/simulate", {method: "POST"});
    if (!response.ok) throw new Error("simulation failed");
    const data = await response.json();
    document.querySelector("#summary").hidden = false;
    const summary = document.querySelector("#summary");
    summary.replaceChildren();
    summary.append(`AI: ${data.ai_mode === "openai" ? "OpenAI API" : data.ai_mode === "mixed" ? "OpenAI API＋フォールバック混在" : "決定論フォールバック"}　seed: ${data.seed}`);
    const branches = document.querySelector("#branches");
    branches.replaceChildren();
    data.branch_order.forEach(branch => {
      const axes = data.branches[branch].final_state.axes;
      const proposal = data.ai_proposals[branch];
      const article = document.createElement("article");
      const title = document.createElement("h2"); title.textContent = labels[branch];
      const proposalText = document.createElement("p"); proposalText.className = "proposal";
      proposalText.textContent = `提案 (${proposal.source}): ${proposal.action} — ${proposal.rationale}`;
      article.append(title, proposalText);
      Object.entries(axes).forEach(([axis, value]) => {
        const row = document.createElement("div"); row.className = "axis";
        const name = document.createElement("span"); name.textContent = labels[axis];
        const meter = document.createElement("meter"); meter.min = 0; meter.max = 100; meter.value = value;
        const score = document.createElement("b"); score.textContent = value;
        row.append(name, meter, score); article.append(row);
      });
      branches.append(article);
    });
    const trace = document.querySelector("#trace");
    trace.hidden = false;
    trace.querySelector("pre").textContent = JSON.stringify({demo_hash:data.demo_hash, comparison_hash:data.comparison_hash, exogenous_event_stream_hash:data.exogenous_event_stream_hash, first_turns:Object.fromEntries(data.branch_order.map(b => [b,data.branches[b].events[0]]))}, null, 2);
    status.textContent = "3分岐×4ラウンド完走。結果と因果トレースを表示しました。";
  } catch (_) {
    status.textContent = "実行に失敗しました。サーバーのログを確認してください。";
  }
});
