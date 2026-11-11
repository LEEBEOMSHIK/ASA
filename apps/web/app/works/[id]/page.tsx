import {notFound} from "next/navigation";
import {CustomerWorkspace} from "../../../components/customer-workspace";
import {workRoute} from "../../../lib/work-route";
export default async function WorkPage({params}:{params:Promise<{id:string}>}){const {id}=await params;if(!workRoute(new URL(`/works/${id}`,"http://local")))notFound();return <CustomerWorkspace/>;}
