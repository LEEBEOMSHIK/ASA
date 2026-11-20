export function videoRetryEligible(review:{eligible:boolean;target:unknown;original:{provider_task:string|null}}|null):boolean {
  return !!review?.eligible&&!!review.target&&!review.original.provider_task;
}

export function videoRetryReady(eligible:boolean,needsConfirmation:boolean,confirmed:boolean,busy:boolean,loading:boolean):boolean {
  return eligible&&(!needsConfirmation||confirmed)&&!busy&&!loading;
}
