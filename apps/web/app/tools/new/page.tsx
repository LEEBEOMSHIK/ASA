import { RegistryShell } from "../../../components/registry-shell";
import { Card, StatusBadge } from "../../../components/ui";
export default function NewToolPage() {
  return <RegistryShell><a href="/tools">← 도구 목록</a><div className="page-heading"><div><p className="eyebrow">CREATE A TOOL</p><h1>어떤 도구를 만들까요?</h1><p className="muted">AI에게 맡길 일은 직접 만들고, 새로운 프로그램 기능은 개발자가 연결합니다.</p></div></div>
    <div className="tool-example-grid"><Card><StatusBadge tone="success">직접 만들 수 있어요</StatusBadge><h2>에이전트를 도구로 만들기</h2><p>대본 작성, 제목 추천, 문장 검토처럼 AI에게 맡길 역할을 정하세요.</p><ol><li>에이전트를 만들고 맡길 일을 적습니다.</li><li>실행할 때 전달할 정보를 설정합니다.</li><li>저장하고 ‘도구로 등록’하면 다른 에이전트에서 선택할 수 있습니다.</li></ol><p className="muted">등록된 버전이 도구 목록에 표시됩니다. 실제 AI 실행 연결은 준비 중입니다.</p><div className="actions"><a className="button button--primary" href="/agents/new">에이전트로 도구 만들기</a><a href="/agents">기존 에이전트에서 등록하기 →</a></div></Card>
    <Card><StatusBadge>개발자가 구현해요</StatusBadge><h2>ASA 기본 도구 추가하기</h2><p>영상 합성, 파일 처리, 외부 서비스 연동처럼 프로그램이 수행할 기능은 개발 작업이 필요합니다.</p><p>개발자가 기능과 입력·결과 형식을 구현하고 권한, 오류 처리, 버전을 관리한 뒤 ASA 도구로 제공합니다.</p><p className="muted">현재 범위에서는 사용자 코드 실행이나 임의의 외부 API를 연결하는 생성기는 제공하지 않습니다.</p></Card></div>
  </RegistryShell>;
}
