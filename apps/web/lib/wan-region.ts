import type {VideoConnectionCheck} from "./video-connection";

export type WanRegionState = {
  active_region: string; revision: number;
  regions: {region:string; label:string; connection_state:string; connection_check?:VideoConnectionCheck}[];
};
export type WanRegionProof = {region:string; revision:number; check:VideoConnectionCheck};

export function canApplyWanRegion(state:WanRegionState, target:string, proof:WanRegionProof|null):boolean {
  const age=proof?.check.checked_at ? Date.now()-Date.parse(proof.check.checked_at) : NaN;
  return target!==state.active_region && proof?.region===target && proof.revision===state.revision
    && state.regions.some(region=>region.region===target&&region.connection_state==="configured")
    && proof.check.status==="authenticated" && age>=0 && age<5*60*1000;
}
