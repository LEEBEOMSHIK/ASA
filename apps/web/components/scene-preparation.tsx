import { Card, StatusBadge } from "./ui";

export function ScenePreparation({ value, active }: { value: unknown; active: boolean }) {
  const plan = value && typeof value === "object" ? value as Record<string, unknown> : {};
  const shots = Array.isArray(plan.shots) ? plan.shots.filter((s): s is Record<string, unknown> => !!s && typeof s === "object") : [];
  return <Card>
    <div className="card-heading"><h3>장면별 이미지 준비</h3><StatusBadge tone="warning">{active ? "분석 중" : "분석 중단"}</StatusBadge></div>
    <p className="muted">{active ? "장면별 구도와 캐릭터 기준을 정리하고 있습니다. 분석이 완료되면 각 장면에서 이미지를 생성할 수 있습니다." : "분석이 끝나지 않아 이미지 생성을 시작할 수 없습니다. 아래 장면은 작성 중이던 내용이며, 완료된 결과가 아닙니다."}</p>
    <div className="scene-preparation-grid" aria-label="분석 중인 장면">
      {shots.map((shot, i) => <div className="scene-preparation-item" key={i}>
        <span className="helper-text">장면 {i + 1}</span>
        <strong>{typeof shot.title === "string" ? shot.title : "장면 정리 중"}</strong>
        <span className="helper-text">{active ? "이미지 제작 계획 작성 중" : "미완성 · 다시 분석 필요"}</span>
      </div>)}
    </div>
    {!shots.length && <p className="helper-text">대본·장면 구성과 첨부한 캐릭터 자료를 확인하고 있습니다.</p>}
  </Card>;
}
