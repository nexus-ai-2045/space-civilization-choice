import Phaser from 'phaser';
import './style.css';
import './responsive.css';
import {controls,defaults,normalizeAllocations} from './data';
import type {ProgressEvent,RoundView,SimulationResult} from './types';
import {ConstellationScene} from './ConstellationScene';

const app=document.querySelector<HTMLDivElement>('#app')!;
let params={...defaults};
let latest:SimulationResult|null=null;
let selectedRound=1;
let game:Phaser.Game|null=null;
let runGeneration=0;
let replayTimer:number|undefined;
let activeRun:AbortController|undefined;
const ANNUAL_ROUNDS=15;
const prefersReducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');

app.innerHTML=`<header><div><strong>CAUSAL CONSTELLATION</strong><h1>宇宙文明の選択肢を、同じ未来条件で比較する</h1></div><div class="mode">ローカル・マルチエージェントPDCA（2026–2040年）</div><label>シナリオ名<input value="デフォルトシナリオ" aria-label="シナリオ名"></label></header><main><aside class="panel controls"><h2>パラメータを編集</h2><div id="control-list"></div><button id="run">▶ シミュレーションを実行</button><output id="status" aria-live="polite">実行待ち</output><p class="progress-note">実際の年次イベントで進捗を表示し、計算完了後に結果をリプレイします。</p></aside><section class="stage"><div id="game" aria-label="三領域の因果コンステレーション"></div><div class="legend">→ 因果リンク　⋯ フィードバックループ　✦ 選択された介入パス</div><section class="timeline"><h2>シミュレーションタイムライン（年ごと完全PDCA・2026–2040年）</h2><div id="rounds" aria-label="年次結果"></div></section></section><aside class="panel evidence"><h2>エビデンス＆トレース</h2><div id="current"></div><p id="engine"></p><p id="replay-hash" class="replay-hash"></p><h3>提案と意思決定</h3><div id="proposals"></div><h3>主体間の応答と再提案</h3><div id="interactions"></div><h3>アウトプット指標（6軸）</h3><div id="axes"></div><details><summary>因果トレースを表示</summary><ol id="trace"></ol></details></aside></main><footer>本シミュレーションは仮説的な因果関係に基づく探索的分析であり、実在の未来を保証するものではありません。<span>● ローカル実行モード</span></footer>`;

function el<K extends keyof HTMLElementTagNameMap>(tag:K,cls?:string,text?:string){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n}
function clear(q:string){const n=document.querySelector(q)!;n.replaceChildren();return n}
function syncControlLabels(){
 document.querySelectorAll<HTMLInputElement>('#control-list input[type=range]').forEach(input=>{
  const key=input.dataset.key!;
  const value=params[key];
  input.value=String(value);
  const label=document.querySelector(`#v${input.dataset.i}`);
  if(label)label.textContent=(value/100).toFixed(2);
 });
}

const list=document.querySelector('#control-list')!;
let activeKind='';
controls.forEach((c,i)=>{
 if(c.kind!==activeKind){
  activeKind=c.kind;
  list.append(el('h3','control-group',({allocation:'予算配分（合計100）',strategy:'戦略',initial:'初期状態',uncertainty:'不確実性'} as const)[c.kind]));
 }
 const label=el('label','control'),head=el('span'),name=el('span','',c.label),value=el('b','',(c.value/100).toFixed(2)),input=el('input') as HTMLInputElement;
 value.id=`v${i}`;head.append(name,value);input.type='range';input.min='0';input.max='100';input.value=String(c.value);input.dataset.key=c.id;input.dataset.i=String(i);input.setAttribute('aria-label',c.label);label.append(head,input);list.append(label);
});
list.addEventListener('input',e=>{
 const t=e.target as HTMLInputElement;
 if(t.type==='range'){
  params[t.dataset.key!]=+t.value;
  document.querySelector(`#v${t.dataset.i}`)!.textContent=(+t.value/100).toFixed(2);
 }
});

function viewFor(result:SimulationResult,round:number):RoundView{
 if(result.rounds&&result.rounds.length){
  const found=result.rounds.find(item=>item.round===round)||result.rounds[result.rounds.length-1];
  return found;
 }
 return {round:result.round,year:result.year,axes:result.axes,proposals:result.proposals,interactions:[],trace:result.trace,domains:result.proposals.filter(p=>p.accepted).map(p=>p.domain||'').filter(Boolean),accepted_actions:result.proposals.filter(p=>p.accepted).map(p=>p.action_id||'').filter(Boolean)};
}

function publishScene(view:RoundView){
 const scene=game?.scene.getScene('constellation') as ConstellationScene|undefined;
 if(!scene||!scene.sys?.isActive())return;
 scene.applySimulation({
  domains:view.domains||view.proposals.filter(p=>p.accepted).map(p=>p.domain||'').filter(Boolean),
  acceptedActions:view.accepted_actions||view.proposals.filter(p=>p.accepted).map(p=>p.action_id||'').filter(Boolean),
  axes:view.axes,
 });
}

function render(result:SimulationResult,round=selectedRound){
 latest=result;
 selectedRound=round;
 const view=viewFor(result,round);
 const roundCount=result.rounds?.length||result.round||1;
 const current=clear('#current'),box=el('div','current');
 box.append(el('span','','現在のラウンド'));
 const strong=el('strong','',String(view.year));
 strong.append(el('small','',`（年次 ${view.round} / ${roundCount}）`));
 box.append(strong,el('span','','当該年のPDCA: 計画 → 実行 → 評価 → 改善（完了）'),el('span','',`完了年次 ${view.round} / ${roundCount}`));
 current.append(box);
 document.querySelector('#engine')!.textContent=`意思決定エンジン: ${result.decision_engine}`;
 const hashNode=document.querySelector('#replay-hash')!;
 const hash=result.canonical_output_hash||'';
 hashNode.textContent=hash?`再実行hash: ${hash}`:'再実行hash: （未取得）';
 hashNode.setAttribute('title',hash||'');
 const proposals=clear('#proposals');
 view.proposals.forEach(p=>{
  const row=el('div',`proposal ${p.accepted?'yes':'no'}`),title=el('span','',`${p.accepted?'✓':'×'} ${p.title}`),score=el('b','',`${p.score>0?'+':''}${p.score}`);
  title.title=`提案主体: ${p.agent}`;
  row.append(title,score,el('small','proposal-rationale',p.rationale));
  proposals.append(row);
 });
 const interactions=clear('#interactions');
 const stanceLabel={support:'支持',oppose:'反対',amend:'修正要求'} as const;
 view.interactions.forEach(item=>{
  const row=el('div','interaction');
  row.append(
   el('b','',`${item.responder_agent_id} → ${item.target_agent_id}: ${stanceLabel[item.stance]}`),
   el('span','',`${item.initial_action} → ${item.final_action}（優先度 ${item.priority_delta>=0?'+':''}${item.priority_delta}、最終 ${item.final_priority}）`),
   el('small','',item.rationale),
  );
  interactions.append(row);
 });
 const axes=clear('#axes');
 view.axes.forEach(a=>{
  const row=el('div','axis'),bar=el('i');
  bar.style.setProperty('--c',/^#[0-9a-f]{6}$/i.test(a.color)?a.color:'#31aaff');
  bar.style.setProperty('--v',`${Math.max(0,Math.min(100,a.value))}%`);
  row.append(el('span','',a.label),bar,el('b','',(a.value/100).toFixed(2)));
  axes.append(row);
 });
 const trace=clear('#trace');
 (view.trace.length?view.trace:result.trace).forEach(x=>trace.append(el('li','',x)));
 const rounds=clear('#rounds');
 const roundViews=result.rounds?.length?result.rounds:[view];
 roundViews.forEach((roundView,i)=>{
  const roundNumber=roundView.round||i+1;
  const b=el('button',`round ${roundNumber===view.round?'active':''}`) as HTMLButtonElement;
  b.type='button';
  b.dataset.round=String(roundNumber);
  b.setAttribute('aria-label',`${roundView.year}年、年次${roundNumber}の結果を表示`);
  b.setAttribute('aria-current',roundNumber===view.round?'step':'false');
  b.append(el('b','',String(roundView.year)),el('span','',`年次 ${roundNumber} · Plan→Do→Check→Act`));
  b.addEventListener('click',()=>{window.clearTimeout(replayTimer);document.querySelector('#status')!.textContent=`結果リプレイを停止・${roundView.year}年を表示`;if(latest)render(latest,roundNumber)});
  rounds.append(b);
 });
 publishScene(view);
}

async function runSimulation(){
 activeRun?.abort();
 const controller=new AbortController();
 activeRun=controller;
 const generation=++runGeneration;
 window.clearTimeout(replayTimer);
 const s=document.querySelector('#status')!;
 s.textContent='5主体が15年分を計算中…';
 params=normalizeAllocations(params);
 syncControlLabels();
 try{
  const request={method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({parameters:params,rounds:ANNUAL_ROUNDS})};
  const res=await fetch('/api/simulate/stream',{...request,signal:controller.signal});
  if(!res.ok)throw new Error(String(res.status));
  if(!res.body)throw new Error('進捗ストリームを取得できません');
  const reader=res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer='';
  let result:SimulationResult|undefined;
  const handleEvent=(event:ProgressEvent)=>{
   if(generation!==runGeneration)return;
   if(event.event==='year_started')s.textContent=`${event.year}年: 5主体が提案を作成中…`;
   if(event.event==='interaction_completed')s.textContent=`${event.year}年: 主体間の応答・再提案を完了`;
   if(event.event==='year_completed')s.textContent=`${event.year}年: 年次PDCA完了（${event.round||event.year-2025} / ${ANNUAL_ROUNDS}）`;
   if(event.event==='simulation_completed')result=event.result;
  };
  while(true){
   const {done,value}=await reader.read();
   if(generation!==runGeneration){await reader.cancel();return}
   buffer+=value||'';
   const lines=buffer.split('\n');
   buffer=lines.pop()||'';
   lines.filter(Boolean).forEach(line=>handleEvent(JSON.parse(line) as ProgressEvent));
   if(done)break;
  }
  if(buffer.trim())handleEvent(JSON.parse(buffer) as ProgressEvent);
  if(!result)throw new Error('完了イベントに結果がありません');
  const finalResult=result;
  if(generation!==runGeneration)return;
  const roundCount=finalResult.rounds?.length||finalResult.round||1;
  if(prefersReducedMotion.matches||roundCount<2){
   selectedRound=roundCount;render(finalResult,selectedRound);s.textContent=`計算完了（${roundCount}年次）`;
  }else{
   selectedRound=1;render(finalResult,selectedRound);s.textContent=`計算完了・${roundCount}年次の結果をリプレイ中`;
   const advance=()=>{if(generation!==runGeneration)return;if(selectedRound>=roundCount){s.textContent=`計算・リプレイ完了（${roundCount}年次）`;return}selectedRound+=1;render(finalResult,selectedRound);replayTimer=window.setTimeout(advance,280);};
   replayTimer=window.setTimeout(advance,280);
  }
 }catch(error){
  if(generation!==runGeneration)return;
  if(error instanceof DOMException&&error.name==='AbortError')return;
  s.textContent=`実行失敗: ${error instanceof Error?error.message:'unknown'}`;
 }finally{if(activeRun===controller)activeRun=undefined}
}

document.querySelector('#run')!.addEventListener('click',runSimulation);
game=new Phaser.Game({type:Phaser.AUTO,parent:'game',transparent:true,scene:[ConstellationScene],scale:{mode:Phaser.Scale.RESIZE,width:'100%',height:'100%'},render:{antialias:true}});
game.events.once('ready',()=>{void runSimulation()});
