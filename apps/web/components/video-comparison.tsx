"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { estimateVideoCost, runwayPricingSource, videoCandidates } from "../lib/video-comparison";
import { videoApiGuides } from "../lib/video-api-guides";
import { Button, ExternalLink, StatusBadge } from "./ui";
import styles from "./video-comparison.module.css";

type Catalog = { models: { provider: string; model: string }[]; enabled: boolean; key_configured: boolean; worker_online: boolean };
const money = (value: number) => `₩${Math.round(value).toLocaleString("ko-KR")}`;

export function VideoComparison() {
  const [seconds, setSeconds] = useState(60);
  const [exchange, setExchange] = useState("1325");
  const [baselineId, setBaselineId] = useState("seedance25");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(["runway", "seedance25", "wan"]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  async function refresh() {
    setLoading(true); setError("");
    try { setCatalog(await api<Catalog>("/video-planning/models")); }
    catch { setError("연동 상태를 불러오지 못했습니다."); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  const validRate = Number.isFinite(Number(exchange)) && Number(exchange) > 0;
  const rate = validRate ? Number(exchange) : 1325;
  const rows = videoCandidates.map(candidate => ({ ...candidate, ...estimateVideoCost(candidate, seconds, rate) })).sort((a, b) => a.won - b.won);
  const baseline = rows.find(row => row.id === baselineId) ?? rows[0];
  const cheapest = rows[0];
  const maximum = rows[rows.length - 1].won;
  const shown = rows.filter(row => `${row.name} ${row.family}`.toLowerCase().includes(query.toLowerCase()));
  const details = rows.filter(row => selected.includes(row.id));
  const durationLabel = seconds < 60 ? `${seconds}초` : `${seconds / 60}분 (${seconds}초)`;
  const ready = !!catalog?.key_configured && !!catalog?.enabled && !!catalog?.worker_online;
  const status = error || (loading ? "확인 중" : !catalog ? "확인 전" : !catalog.key_configured ? "API 키 미설정" : !catalog.enabled ? "영상 생성 꺼짐" : !catalog.worker_online ? "영상 워커 오프라인" : "서버 설정 준비됨");
  function toggle(id: string) { setSelected(previous => previous.includes(id) ? previous.filter(value => value !== id) : previous.length < 3 ? [...previous, id] : previous); }
  return <main className={styles.page}>
    <header className={styles.header}><p className={styles.eyebrow}>VIDEO AI COMPARISON</p><h1>영상 AI 비교</h1><p>얼마나 차이 나는지, 어떤 조건이 유리한지 같은 기준으로 비교하세요.</p><StatusBadge>공급자 선택 전 · 비교용</StatusBadge></header>
    <section className={styles.controls} aria-label="비용 비교 조건">
      <label>완성 영상 1편의 목표 길이<select value={seconds} onChange={event => setSeconds(Number(event.target.value))}><option value={30}>30초</option><option value={60}>1분</option><option value={180}>3분</option><option value={300}>5분</option></select></label>
      <label>차액 비교 기준<select value={baselineId} onChange={event => setBaselineId(event.target.value)}>{videoCandidates.map(model => <option value={model.id} key={model.id}>{model.name}</option>)}</select></label>
      <label>환산 기준 · 원 / 1달러<input type="number" min="1" step="1" value={exchange} onChange={event => setExchange(event.target.value)} aria-invalid={!validRate} /><small>{validRate ? "실시간 환율 아님 · 비교용으로 조정할 수 있어요" : "양수를 입력하세요. 현재 계산은 1,325원 기준입니다."}</small></label>
    </section>
    <section className={styles.basis} aria-label="현재 가격 계산 기준" aria-live="polite">
      <h2>아래 가격은 {durationLabel} 영상 1편 기준입니다</h2>
      <p>필요한 클립을 각각 한 번 생성하고 이어 붙이는 경우입니다. 마음에 들지 않아 다시 만드는 비용은 포함하지 않습니다.</p>
      <p><strong>{baseline.name} 계산 예</strong> · 클립 1개({baseline.seconds}초) {money(baseline.won / baseline.clips)} × {baseline.clips}개 = <strong>{money(baseline.won)}</strong></p>
      <p className={styles.footnote}>목표 {seconds}초 → {baseline.seconds}초 클립 {baseline.clips}개 → 총 {baseline.generatedSeconds}초 생성. 클립 길이로 나누어떨어지지 않으면 올림 계산하며 남는 부분은 편집합니다. 같은 분량을 전부 한 번 더 생성하면 영상 생성 비용은 약 {money(baseline.won * 2)}입니다.</p>
    </section>
    <div className={styles.notice}><strong>구매 경로가 다른 가격의 참고 비교입니다.</strong><p>Runway는 공식 API 요금, 나머지는 제공하신 힉스필드 가격표입니다. 동일 API 견적이 아니며 할인·구독 조건과 해상도가 다릅니다. 비교 기준을 바꿔도 실제 생성 모델은 변경되지 않습니다.</p></div>
    <section className={styles.highlights} aria-label="비용 차이 요약">
      <article><span>비교 기준 · {baseline.name}</span><strong>{money(baseline.won)}</strong><small>{seconds}초 제작 · {baseline.clips}개 클립</small></article>
      <article className={styles.saving}><span>자료상 최저 예상 비용 · {cheapest.name}</span><strong>{money(cheapest.won)}</strong><small>{durationLabel} 영상 1편 · {cheapest.clips}개 클립<br/>{baseline.won > cheapest.won ? `기준보다 ${money(baseline.won - cheapest.won)} 낮음 · ${Math.round((1 - cheapest.won / baseline.won) * 100)}% 절감` : "현재 비교 기준이 자료상 최저 비용입니다."}</small></article>
      <article><span>가격 외에 비교할 차이</span><strong className={styles.feature}>10초 vs 15초 클립</strong><small>{seconds}초 기준 {Math.ceil(seconds / 10)}개 vs {Math.ceil(seconds / 15)}개 · 긴 클립은 연결할 구간이 적습니다.</small></article>
    </section>
    <section className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>{durationLabel} 영상 1편 · 예상 생성 비용</h2><p>낮은 가격순 · 각 클립 1회 생성 · 최대 3개를 골라 아래에서 상세 비교</p></div><label className={styles.search}><span className="sr-only">모델 검색</span><input placeholder="모델 검색" value={query} onChange={event => setQuery(event.target.value)} /></label></div>
      <div className={styles.tableScroll}><table className={styles.table}><caption className="sr-only">{seconds}초 영상 비용 및 {baseline.name} 대비 차이</caption><thead><tr><th scope="col">비교</th><th scope="col">모델 / 가격 출처</th><th scope="col">예상 비용 · 원</th><th scope="col">{baseline.name} 대비</th><th scope="col">클립 / 해상도</th></tr></thead><tbody>{shown.map(row => {
        const delta = row.won - baseline.won;
        return <tr key={row.id} className={selected.includes(row.id) ? styles.selectedRow : undefined}><td><button className={styles.pick} aria-label={`${row.name} 상세 비교 ${selected.includes(row.id) ? "해제" : "선택"}`} aria-pressed={selected.includes(row.id)} disabled={!selected.includes(row.id) && selected.length >= 3} onClick={() => toggle(row.id)}>{selected.includes(row.id) ? "✓" : "+"}</button></td><th scope="row"><strong>{row.name}</strong><small>{row.id === "runway" ? "공식 API" : "힉스필드 · 제공 자료"}</small></th><td><strong className={styles.price}>{money(row.won)}</strong><small>{durationLabel} 1편<br/>{money(row.won / row.clips)} / {row.seconds}초 클립 × {row.clips}개</small><div className={styles.barTrack} aria-hidden="true"><div style={{ width: `${row.won / maximum * 100}%` }} /></div></td><td><span className={delta < 0 ? styles.lower : delta > 0 ? styles.higher : styles.muted}>{delta === 0 ? "비교 기준" : `${delta < 0 ? "−" : "+"}${money(Math.abs(delta))}`}</span>{delta !== 0 && <small>{Math.abs(delta / baseline.won * 100).toFixed(1)}% {delta < 0 ? "낮음" : "높음"}</small>}</td><td>{row.clips}개 × {row.seconds}초<small>{row.resolution}{row.id !== "runway" ? " · 제공 자료" : " · 설정 기준"}{row.generatedSeconds !== seconds ? ` · ${row.generatedSeconds}초 과금` : ""}</small></td></tr>;
      })}</tbody></table></div>
      {!shown.length && <p className={styles.empty}>검색에 맞는 모델이 없습니다.</p>}
      <p className={styles.footnote}>영상 클립 생성만의 예상 비용입니다. 대본·비디오 프롬프트 작성 AI, 씬 이미지 생성, 재생성, 편집·음성·세금·구독료는 별도입니다. 최종 완성 영상의 전체 제작비가 아니며 실제 청구액은 공급자 조건에 따라 달라집니다.</p>
    </section>
    <section className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>선택 모델, 무엇이 다른가요?</h2><p>성능 순위가 아닌 비용·제작 조건·연동 준비도를 비교합니다.</p></div><span>{selected.length} / 3개 선택</span></div>
      {details.length ? <div className={styles.detailGrid} style={{ gridTemplateColumns: `repeat(${details.length}, minmax(0, 1fr))` }}>{details.map(row => <article className={styles.detail} key={row.id}><h3>{row.name}</h3><dl>
        <dt>확인 가능한 이점</dt><dd>{row.id === cheapest.id ? "자료상 예상 비용이 가장 낮습니다. " : ""}{row.id === "runway" ? "ASA에 생성 경로가 구현되어 있어 추가 연동 작업이 적습니다. 공급자 채택을 의미하지 않습니다." : row.resolution === "2K" ? "제공 자료상 2K 출력. 다른 720p 후보보다 해상도 조건이 높지만 화질 우위는 미검증입니다." : row.seconds === 15 ? `15초 단위로 ${seconds}초를 ${row.clips}개로 구성해 10초 단위보다 연결 구간이 적습니다.` : "10초 단위 제작 조건입니다. 가격 외의 품질 이점은 아직 검증되지 않았습니다."}</dd>
        <dt>확인할 품질 항목</dt><dd>{row.focus}</dd><dt>ASA 적용에 필요한 일</dt><dd>{row.id === "runway" ? "API 키·잔액·인증 및 실제 생성 확인" : "정확한 API 모델명·요금·참조 이미지 지원 확인 후 생성 경로 구현"}</dd><dt>실제 품질 비교</dt><dd><StatusBadge>동일 씬 테스트 미실시</StatusBadge></dd>
      </dl></article>)}</div> : <p>위 목록에서 비교할 모델을 선택하세요.</p>}
    </section>
    <section className={`${styles.panel} ${styles.integration}`} aria-label="API 연동 방법">
      <h2>모델별 API 연동 방법</h2>
      <p>비교표의 9개 모델을 모두 안내합니다. 각 항목을 펼치면 키 준비, 요청·결과 조회와 공식 출처를 볼 수 있습니다. 문서 확인은 실제 연결 성공을 의미하지 않습니다.</p>
      <p className={styles.footnote}>직접 API는 모델 공급자와, 중개 API는 Runway와 계약·과금합니다. 위 힉스필드 가격은 아래 API 요금이 아닙니다. 확인일: 2026-11-06.</p>
      <div className={styles.apiList}>{videoApiGuides.map(guide => <details className={styles.apiGuide} key={guide.id}>
        <summary><span className={styles.apiTitle}>{videoCandidates.find(model => model.id === guide.id)?.name}</span><span className={styles.apiRoute}>{guide.route}</span></summary>
        <div className={styles.apiBody}>
          <dl>
            <div><dt>모델 ID</dt><dd><code>{guide.model}</code></dd></div>
            <div><dt>1. 계정·인증 준비</dt><dd>{guide.setup}</dd></div>
            <div><dt>2. 생성 요청</dt><dd>{guide.request}</dd></div>
            <div><dt>3. 완료·결과 조회</dt><dd>{guide.result}</dd></div>
            <div><dt>제한·확인할 사항</dt><dd>{guide.note}</dd></div>
            <div><dt>ASA 적용 상태</dt><dd>{guide.id === "wan" ? "WAN 3.0 직접 생성 경로 구현됨 · 서버에 ASA_WAN_API_KEY, ASA_WAN_WORKSPACE_ID, ASA_WAN_REGION을 설정하고 영상 생성을 활성화합니다. 에이전트 설정의 영상 모델 선택지에 wan3를 추가하고 저장한 뒤 새 실행에서 선택하세요. 초기 연결은 720p·2~30초입니다. 실제 인증·생성은 별도 검증이 필요합니다." : guide.id === "runway" ? "생성 경로 구현됨 · 아래 서버 설정 절차 참고" : "추가 구현 필요 · 키를 등록하거나 모델 ID만 바꿔서는 사용할 수 없습니다. 모델 설정·입력 검증·생성/조회·결과 저장 경로를 연결해야 합니다."}</dd></div>
          </dl>
          <div className={styles.linkRow}>{guide.sources.map(source => <ExternalLink key={source.href} href={source.href}>{source.label}</ExternalLink>)}</div>
        </div>
      </details>)}</div>
      <h2>ASA에 구현된 Runway 경로 연결</h2>
      <p>현재 ASA에는 Runway Gen-4.5 영상 생성 경로가 구현되어 있습니다. 아래는 연결 방법 안내이며, 이 화면에서 키 등록이나 유료 생성을 실행하지 않습니다.</p>
      <ol>
        <li><strong>Runway 개발자 계정 준비</strong><p>개발자 포털에서 프로젝트를 만들고 API 키를 발급한 뒤 API 크레딧을 충전합니다. 웹 서비스 구독 가격과 이 화면의 API 단가를 구분해 확인하세요.</p><ExternalLink href="https://docs.dev.runwayml.com/guides/setup/">계정·API 키·크레딧 공식 안내</ExternalLink></li>
        <li><strong>ASA 서버에 연결 설정</strong><p>관리자가 서버의 비밀 설정에 키를 등록하고 영상 생성을 활성화합니다. 키를 이 화면이나 프롬프트에 붙여 넣지 마세요.</p><details><summary>관리자용 설정 이름과 실행 방법</summary><p>서버 .env의 <code>ASA_RUNWAY_API_KEY</code>에 발급한 키, <code>ASA_VIDEO_AI_ENABLED=true</code>를 설정한 뒤 API 프로세스를 재시작합니다. 같은 환경에서 영상 워커를 실행합니다.</p><code className={styles.command}>uv run --locked --project services/backend python -m asa.video_worker</code><p>워커를 시작하면 이미 대기 중인 영상 생성 요청도 처리할 수 있습니다.</p></details></li>
        <li><strong>연결 상태 확인</strong><p>아래 상태를 새로고침하고, 비디오 프롬프트 실행 화면의 Runway 모델 옆 연결 확인 버튼으로 계정 인증을 확인합니다. 키 설정·워커 온라인만으로 잔액이나 생성 성공까지 보장되지는 않습니다.</p></li>
        <li><strong>씬 이미지와 프롬프트로 짧은 클립 테스트</strong><p>확정 씬 이미지를 선택하고 비디오 프롬프트를 작성한 다음 영상 생성 요청을 실행합니다. 프롬프트 작성 AI 비용과 영상 생성 비용은 따로 발생합니다. 먼저 한 클립의 결과·실제 비용을 확인한 뒤 제작 범위를 늘리세요.</p></li>
      </ol>
      <details><summary>API 처리 흐름과 다른 모델 추가</summary><p>ASA 서버가 이미지와 프롬프트를 Runway의 <code>POST /v1/image_to_video</code>로 전송하고, 워커가 작업 상태를 조회해 완료된 영상을 가져옵니다. API 키는 서버에서만 사용합니다.</p><p>다른 후보는 표의 표시 이름을 그대로 API 모델 ID로 사용하면 안 됩니다. 공급자 또는 중개 API에서 정확한 모델 ID·I2V 지원·길이·해상도·API 요금을 확인하고, ASA의 모델 설정과 생성·상태 조회·결과 저장 경로를 연결해야 합니다. Runway API가 제공하는 모델도 현재 ASA 구현에서는 Gen-4.5 외 추가 연결 작업이 필요합니다. 힉스필드 제공 자료의 금액을 API 호출 단가로 사용하지 마세요.</p><div className={styles.linkRow}><ExternalLink href="https://docs.dev.runwayml.com/api/">공식 API 요청 형식</ExternalLink><ExternalLink href="https://docs.dev.runwayml.com/guides/models/">API 모델 목록</ExternalLink></div></details>
      <p className={styles.footnote}>공식 연동 문서 확인: 2026-11-06. 이 비교 화면에서는 API 설정이나 영상 생성을 실행하지 않습니다.</p>
    </section>
    <details className={styles.panel}><summary>연동 준비 상태 · 공급자 선택과 별개</summary><div className={styles.connection}><div><strong>Runway 생성 경로</strong><p>현재 구현된 경로입니다. 사용할 공급자를 확정한 상태는 아닙니다.</p></div><StatusBadge tone={ready ? "success" : "warning"}>{status}</StatusBadge><Button variant="secondary" disabled={loading} onClick={refresh}>상태 새로고침</Button></div><p className={styles.footnote}>서버 설정과 워커 상태만 확인합니다. API 인증·잔액·생성 성공을 보장하지 않습니다.</p></details>
    <footer className={styles.sources}><ExternalLink href={runwayPricingSource}>Runway 공식 API 가격 근거</ExternalLink><p>Runway: 12크레딧/초 × $0.01. 다른 후보의 표 가격은 제공된 힉스필드 자료이며 최신 가격은 미확인입니다. API 경로와 확인 한계는 모델별 안내를 참고하세요. 화질 우열은 같은 씬 이미지·프롬프트로 생성해 비교한 뒤 판단해야 합니다.</p></footer>
  </main>;
}
