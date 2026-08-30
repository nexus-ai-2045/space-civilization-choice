export type Axis={id?:string;label:string;value:number;color:string};
export type Proposal={agent:string;title:string;score:number;accepted:boolean;action_id?:string;domain?:string;rationale:string};
export type Interaction={responder_agent_id:string;target_agent_id:string;stance:'support'|'oppose'|'amend';priority_delta:number;rationale:string;initial_action:string;final_action:string;final_priority:number};
export type RoundView={round:number;year:number;axes:Axis[];proposals:Proposal[];interactions:Interaction[];trace:string[];accepted_actions?:string[];domains?:string[]};
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
export type ProgressEvent={
 event:'year_started'|'interaction_completed'|'year_completed'|'simulation_completed';
 year:number;
 round?:number;
 canonical_output_hash?:string;
 result?:SimulationResult;
};
export type SimParams=Record<string,number>;
export type ConstellationState={domains:string[];acceptedActions:string[];axes:Axis[]};
