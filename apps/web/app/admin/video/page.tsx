import {RegistryShell} from "../../../components/registry-shell";
import {VideoGenerationManager} from "../../../components/video-generation-manager";
export default function Page(){return <RegistryShell><h1>영상 생성 관리</h1><p className="muted">영상 생성 설정과 공급자 연결 상태를 확인합니다.</p><VideoGenerationManager/></RegistryShell>;}
