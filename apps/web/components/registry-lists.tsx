"use client";
import { useEffect, useState } from "react";
import { api, message, type Agent, type Tool } from "../lib/registry";
import { AgentIcon, Card, StatusBadge } from "./ui";

export function AgentList() {
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Agent[]>("/agents").then(setAgents).catch(e => setError(message(e))); }, []);
  return <><div className="page-heading"><div><p className="eyebrow">YOUR AGENTS</p><h1>나의 에이전트</h1>
    <p className="muted">아이디어부터 대본 검토까지, 반복할 일을 나만의 AI 도우미에게 맡겨 보세요.</p></div>
    <a className="button button--primary" href="/agents/new">+ 에이전트 만들기</a></div>
    <div className="workspace-intro"><div><span className="eyebrow">작게 시작해 보세요</span><h2>첫 도우미, 어렵게 만들 필요 없어요.</h2><p className="muted">역할 예시를 고르고 맡길 일을 다듬으면 됩니다. 복잡한 설정은 나중에 바꿔도 좋아요.</p></div><a href="/agents/new">예시에서 시작하기 →</a></div>
    {error ? <p role="alert">{error}</p> : agents === null ? <p role="status">목록을 불러오는 중입니다…</p> : agents.length === 0 ?
      <Card><h2>첫 에이전트를 만들어 보세요.</h2><p>대본 작가, 기획자, 검수자처럼 나만의 역할을 설정할 수 있습니다.</p></Card> :
      <div className="catalog-grid">{agents.map(agent => <Card key={agent.id} className="agent-catalog-card">
        <div className="card-heading"><AgentIcon icon={agent.draft.icon}/><StatusBadge>저장한 초안</StatusBadge></div><h2><a href={`/agents/${agent.id}`}>{agent.draft.name}</a></h2>
        <p className="muted">{agent.draft.description || "소개를 추가해 이 도우미의 역할을 알려 주세요."}</p><div className="catalog-footer"><span className="muted">연결 도구 {agent.draft.tools.length}개</span><a href={`/agents/${agent.id}`}>설정 편집 →</a></div>
      </Card>)}</div>}</>;
}

export function ToolList() {
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Tool[]>("/tools").then(setTools).catch(e => setError(message(e))); }, []);
  return <><div className="page-heading"><div><p className="eyebrow">TOOL LIBRARY</p><h1>사용할 수 있는 도구</h1>
    <p className="muted">도구를 눌러 사용 방법과 입력·결과 예시를 확인하세요.</p></div></div>
    {error ? <p role="alert">{error}</p> : tools === null ? <p role="status">도구를 불러오는 중입니다…</p> :
      <div className="catalog-grid">{tools.map(tool => <Card key={tool.id}>
        <div className="badge-row"><StatusBadge>{tool.kind === "asa" ? "ASA 도구" : "내 에이전트"}</StatusBadge>
          <StatusBadge tone={tool.launch_path || tool.available ? "success" : "warning"}>{tool.launch_path ? "전용 화면에서 사용" : tool.available ? "등록 가능" : "준비 중"}</StatusBadge></div>
        <h2><a href={`/tools/${encodeURIComponent(tool.id)}`}>{tool.name} <small>v{tool.version}</small></a></h2><p>{tool.description}</p><p className="muted">{tool.unavailable_reason}</p>
        <a href={`/tools/${encodeURIComponent(tool.id)}`}>사용 방법과 예시 보기 →</a>
      </Card>)}</div>}</>;
}
