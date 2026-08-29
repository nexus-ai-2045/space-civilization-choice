export type Axis={id?:string;label:string;value:number;color:string};
export type Proposal={agent:string;title:string;score:number;accepted:boolean;action_id?:string;domain?:string;rationale:string};
export type RoundView={round:number;year:number;axes:Axis[];proposals:Proposal[];trace:string[];accepted_actions?:string[];domains?:string[]};
export type SimulationResult={
 round:number;
 year:number;
 axes:Axis[];
 proposals:Proposal[];
 trace:string[];
 decision_engine:string;
 rounds?:RoundView[];
 canonical_output_hash?:string;
};
export type SimParams=Record<string,number>;
export type ConstellationState={domains:string[];acceptedActions:string[];axes:Axis[]};
