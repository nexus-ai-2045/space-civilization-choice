import Phaser from 'phaser';
import type {ConstellationState} from './types';

type Zone={x:number;y:number;color:number;title:string;nodes:string[];domain:string};
export class ConstellationScene extends Phaser.Scene{
 private reduceMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
 private zones:Zone[]=[];
 private highlight:ConstellationState={domains:[],acceptedActions:[],axes:[]};
 constructor(){super('constellation')}
 create(){this.cameras.main.setBackgroundColor('rgba(0,0,0,0)');this.draw();this.scale.on('resize',()=>this.draw());}
 applySimulation(state:ConstellationState){
  this.highlight={
   domains:[...new Set(state.domains)],
   acceptedActions:[...state.acceptedActions],
   axes:state.axes.map(a=>({...a})),
  };
  this.draw();
 }
 private clearDisplayObjects(){
  // killAll stops tweens; removeAll(true) only detaches and does not destroy textures.
  this.tweens.killAll();
  for (const child of this.children.getAll().slice()) {
   child.destroy(true);
  }
 }
 private draw(){this.clearDisplayObjects();const w=this.scale.width,h=this.scale.height,cx=w/2,cy=h*.5;const r=Math.min(w,h)*.19;
  this.add.rectangle(cx,cy,w,h,0x06111e,0);
  const stars=this.add.graphics();for(let i=0;i<70;i++){const x=(i*83)%w,y=(i*47)%h;stars.fillStyle(i%7?0x174c74:0x42baff,i%7?.25:.8).fillCircle(x,y,i%9?1:1.7)}
  this.zones=[
   {x:cx,y:cy-r*1.15,color:0x9c6cff,title:'認知・文化領域',nodes:['宇宙への憧れ','社会受容','教育・人材'],domain:'cognitive'},
   {x:cx-r*.85,y:cy+r*.65,color:0x18aaff,title:'経済・組織領域',nodes:['価値創造','国際競争力','投資循環'],domain:'economic'},
   {x:cx+r*.85,y:cy+r*.65,color:0xffba35,title:'物理・能力領域',nodes:['宇宙インフラ','技術成熟','輸送能力'],domain:'physical'},
  ];
  const active=new Set(this.highlight.domains);
  const g=this.add.graphics();this.zones.forEach((z,zi)=>{
   const selected=active.size===0||active.has(z.domain);
   g.lineStyle(selected?2:1,z.color,selected?.55:.22);
   for(let j=1;j<=4;j++)g.strokeCircle(z.x,z.y,r*(.43+j*.12));
   const pts=z.nodes.map((_,i)=>{const a=-Math.PI/2+i*Math.PI*2/3;return{x:z.x+Math.cos(a)*r*.54,y:z.y+Math.sin(a)*r*.54}});
   pts.forEach((p,i)=>{
    const n=this.add.circle(p.x,p.y,selected?10:8,z.color,selected?.9:.45).setStrokeStyle(2,0xffffff,selected?.65:.25);
    this.add.text(p.x,p.y-22,z.nodes[i],{fontFamily:'IBM Plex Sans,"Noto Sans JP",sans-serif',fontSize:'11px',color:selected?'#dcecff':'#7f93a8'}).setOrigin(.5);
    if(selected&&!this.reduceMotion)this.tweens.add({targets:n,scale:1.35,alpha:.55,duration:1100+zi*240,yoyo:true,repeat:-1});
   });
   this.add.text(z.x,z.y+r*.72,z.title,{fontFamily:'IBM Plex Sans,"Noto Sans JP",sans-serif',fontSize:'15px',fontStyle:'bold',color:'#'+z.color.toString(16).padStart(6,'0')}).setOrigin(.5);
  });
  const center=this.add.circle(cx,cy+r*.05,42,0x0c3760,.94).setStrokeStyle(2,0x65c9ff,.75);this.add.text(cx,cy+r*.05,'持続可能な\n宇宙文明',{align:'center',fontFamily:'IBM Plex Sans,"Noto Sans JP",sans-serif',fontSize:'13px',fontStyle:'bold',color:'#e8f8ff'}).setOrigin(.5);
  const path=this.add.graphics();
  const linkAlpha=(domain:string)=>(active.size===0||active.has(domain))?0.95:0.2;
  path.lineStyle(3,0xb78cff,linkAlpha('cognitive'));this.link(path,this.zones[0].x,this.zones[0].y+r*.5,cx,cy);
  path.lineStyle(3,0x3abaff,linkAlpha('economic'));this.link(path,this.zones[1].x+r*.45,this.zones[1].y-r*.2,cx-20,cy+20);
  path.lineStyle(3,0xffc74c,linkAlpha('physical'));this.link(path,cx+20,cy+20,this.zones[2].x-r*.45,this.zones[2].y-r*.2);
  if(active.size>1){
   const feedback=this.add.graphics();
   feedback.lineStyle(2,0x7ad7ff,.7);
   feedback.strokeCircle(cx,cy+r*.05,r*1.55);
  }
  const agents=[['政府',.10,0x9c6cff],['研究',.29,0x39aaff],['企業',.47,0x32d4c8],['国際',.72,0xffbb35],['市民',.91,0xff813e]] as const;
  agents.forEach(([name,pos,color])=>{const a=-Math.PI+Math.PI*2*pos;const x=cx+Math.cos(a)*r*2.15,y=cy+Math.sin(a)*r*1.55;this.add.circle(x,y,20,color,.14).setStrokeStyle(2,color,.9);this.add.text(x,y,String(name),{fontFamily:'IBM Plex Sans,"Noto Sans JP",sans-serif',fontSize:'11px',fontStyle:'bold',color:'#e7f5ff'}).setOrigin(.5)});
  if(!this.reduceMotion)this.tweens.add({targets:center,scale:1.08,duration:1400,yoyo:true,repeat:-1,ease:'Sine.inOut'});
 }
 private link(g:Phaser.GameObjects.Graphics,x1:number,y1:number,x2:number,y2:number){g.beginPath().moveTo(x1,y1).lineTo(x2,y2).strokePath()}
}
