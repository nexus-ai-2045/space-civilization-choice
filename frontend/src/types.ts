export type Axis={label:string;value:number;color:string};
export type Proposal={agent:string;title:string;score:number;accepted:boolean};
export type SimulationResult={round:number;year:number;axes:Axis[];proposals:Proposal[];trace:string[];decision_engine:string};
export type SimParams=Record<string,number>;
