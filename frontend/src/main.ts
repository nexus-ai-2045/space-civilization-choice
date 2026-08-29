import Phaser from 'phaser';
import './style.css';
import './responsive.css';
import {controls,defaults,normalizeAllocations} from './data';
import type {RoundView,SimulationResult} from './types';
import {ConstellationScene} from './ConstellationScene';

const app=document.querySelector<HTMLDivElement>('#app')!;
let params={...defaults};
let latest:SimulationResult|null=null;
let selectedRound=4;
let game:Phaser.Game|null=null;

app.innerHTML=`<header><div><strong>CAUSAL CONSTELLATION</strong><h1>宇宙文明の選択肢を、同じ未来条件で比較する</h1></div><div class="mode">ローカル・マルチエージェントPDCA（4ラウンド）</div><label>シナリオ名<input value="デフォルトシナリオ" aria-label="シナリオ名"></label></header><main><aside class="panel controls"><h2>パラメータを編集</h2><div id="control-list"></div><button id="run">▶ シミュレーションを実行</button><output id="status">実行待ち</output></aside><section class="stage"><div id="game" aria-label="三領域の因果コンステレーション"></div><div class="legend">→ 因果リンク　⋯ フィードバックループ　✦ 選択された介入パス</div><section class="timeline"><h2>シミュレーションタイムライン（年ごと完全PDCA × 4）</h2><div id="rounds"></div></section></section><aside class="panel evidence"><h2>エビデンス＆トレース</h2><div id="current"></div><p id="engine"></p><p id="replay-hash" class="replay-hash"></p><h3>提案と意思決定</h3><div id="proposals"></div><h3>アウトプット指標（6軸）</h3><div id="axes"></div><details><summary>因果トレースを表示</summary><ol id="trace"></ol></details></aside></main><footer>本シミュレーションは仮説的な因果関係に基づく探索的分析であり、実在の未来を保証するものではありません。<span>● ローカル実行モード</span></footer>`;

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
 return {round:result.round,year:result.year,axes:result.axes,proposals:result.proposals,trace:result.trace,domains:result.proposals.filter(p=>p.accepted).map(p=>p.domain||'').filter(Boolean),accepted_actions:result.proposals.filter(p=>p.accepted).map(p=>p.action_id||'').filter(Boolean)};
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
 const current=clear('#current'),box=el('div','current');
 box.append(el('span','','現在のラウンド'));
 const strong=el('strong','',String(view.year));
 strong.append(el('small','',`（ラウンド ${view.round} / 4）`));
 box.append(strong,el('span','','当該年のPDCA: 計画 → 実行 → 評価 → 改善（完了）'),el('span','',`経過ターン ${view.round*6} / 24`));
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
  row.append(title,score);
  proposals.append(row);
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
 const years=[2026,2030,2035,2040];
 years.forEach((y,i)=>{
  const b=el('button',`round ${i+1===view.round?'active':''}`) as HTMLButtonElement;
  b.type='button';
  b.dataset.round=String(i+1);
  b.append(el('b','',String(y)),el('span','',`ラウンド ${i+1} · Plan→Do→Check→Act`));
  b.addEventListener('click',()=>{if(latest)render(latest,i+1)});
  rounds.append(b);
 });
 publishScene(view);
}

async function runSimulation(){
 const s=document.querySelector('#status')!;
 s.textContent='5主体が4ラウンド協議中…';
 params=normalizeAllocations(params);
 syncControlLabels();
 try{
  const res=await fetch('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({parameters:params,rounds:4})});
  if(!res.ok)throw new Error(String(res.status));
  const result=await res.json() as SimulationResult;
  selectedRound=result.round||4;
  render(result,selectedRound);
  s.textContent='ローカル決定論シミュレーション完了';
 }catch(error){
  s.textContent=`実行失敗: ${error instanceof Error?error.message:'unknown'}`;
 }
}

document.querySelector('#run')!.addEventListener('click',runSimulation);
game=new Phaser.Game({type:Phaser.AUTO,parent:'game',transparent:true,scene:[ConstellationScene],scale:{mode:Phaser.Scale.RESIZE,width:'100%',height:'100%'},render:{antialias:true}});
game.events.once('ready',()=>{void runSimulation()});
