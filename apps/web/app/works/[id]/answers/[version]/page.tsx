import {notFound} from "next/navigation";
import {CustomerWorkspace} from "../../../../../components/customer-workspace";
import {workRoute} from "../../../../../lib/work-route";
export default async function AnswerPage({params}:{params:Promise<{id:string;version:string}>}){const {id,version}=await params;if(!workRoute(new URL(`/works/${id}/answers/${version}`,"http://local")))notFound();return <CustomerWorkspace/>;}
