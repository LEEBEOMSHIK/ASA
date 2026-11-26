"use client";

import type { ReactNode } from "react";
import { AgentIcon, Button, Card, StatusBadge } from "./ui";

export function WorkspaceStartSteps() {
  return <ol className="customer-steps" aria-label="이용 순서"><li><span>1</span>에이전트 선택</li><li><span>2</span>작업 내용 입력</li><li><span>3</span>결과 확인</li></ol>;
}

export function WorkspaceAgentCard({ name, icon, description, available, favorite, onSelect }: {
  name: string;
  icon?: string;
  description?: string | null;
  available: boolean;
  favorite?: ReactNode;
  onSelect: () => void;
}) {
  return <Card className="customer-agent">
    <div className="card-heading">
      <AgentIcon icon={icon}/>
      <div className="agent-card-controls"><StatusBadge>실행 가능</StatusBadge>{favorite}</div>
    </div>
    <h3>{name}</h3>
    <p className="muted">{description || "필요한 내용을 입력하고 이 에이전트에게 작업을 맡겨 보세요."}</p>
    <Button variant="secondary" disabled={!available} onClick={onSelect} aria-label={name + " 선택하기"}>
      이 에이전트 선택 →
    </Button>
  </Card>;
}
