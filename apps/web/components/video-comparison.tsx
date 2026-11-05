"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/registry";
import { estimateVideoCost, runwayPricingSource, videoCandidates } from "../lib/video-comparison";
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
  const ready = !!catalog?.key_configured && !!catalog?.enabled && !!catalog?.worker_online;
  const status = error || (loading ? "확인 중" : !catalog ? "확인 전" : !catalog.key_configured ? "API 키 미설정" : !catalog.enabled ? "영상 생성 꺼짐" : !catalog.worker_online ? "영상 워커 오프라인" : "서버 설정 준비됨");
  function toggle(id: string) { setSelected(previous => previous.includes(id) ? previous.filter(value => value !== id) : previous.length < 3 ? [...previous, id] : previous); }
  return <main className={styles.page}>
    <header className={styles.header}><p className={styles.eyebrow}>VIDEO AI COMPARISON</p><h1>영상 AI 비교</h1><p>얼마나 차이 나는지, 어떤 조건이 유리한지 같은 기준으로 비교하세요.</p><StatusBadge>공급자 선택 전 · 비교용</StatusBadge></header>
    <section className={styles.controls} aria-label="비용 비교 조건">
      <label>만들 영상 길이<select value={seconds} onChange={event => setSeconds(Number(event.target.value))}><option value={30}>30초</option><option value={60}>1분</option><option value={180}>3분</option><option value={300}>5분</option></select></label>
      <label>차액 비교 기준<select value={baselineId} onChange={event => setBaselineId(event.target.value)}>{videoCandidates.map(model => <option value={model.id} key={model.id}>{model.name}</option>)}</select></label>
      <label>환산 기준 · 원 / 1달러<input type="number" min="1" step="1" value={exchange} onChange={event => setExchange(event.target.value)} aria-invalid={!validRate} /><small>{validRate ? "실시간 환율 아님 · 비교용으로 조정할 수 있어요" : "양수를 입력하세요. 현재 계산은 1,325원 기준입니다."}</small></label>
    </section>
    <div className={styles.notice}><strong>구매 경로가 다른 가격의 참고 비교입니다.</strong><p>Runway는 공식 API 요금, 나머지는 제공하신 힉스필드 가격표입니다. 동일 API 견적이 아니며 할인·구독 조건과 해상도가 다릅니다. 비교 기준을 바꿔도 실제 생성 모델은 변경되지 않습니다.</p></div>
    <section className={styles.highlights} aria-label="비용 차이 요약">
      <article><span>비교 기준 · {baseline.name}</span><strong>{money(baseline.won)}</strong><small>{seconds}초 제작 · {baseline.clips}개 클립</small></article>
      <article className={styles.saving}><span>자료상 최저 예상 비용 · {cheapest.name}</span><strong>{money(cheapest.won)}</strong><small>{baseline.won > cheapest.won ? `기준보다 ${money(baseline.won - cheapest.won)} 낮음 · ${Math.round((1 - cheapest.won / baseline.won) * 100)}% 절감` : "현재 비교 기준이 자료상 최저 비용입니다."}</small></article>
      <article><span>가격 외에 비교할 차이</span><strong className={styles.feature}>10초 vs 15초 클립</strong><small>{seconds}초 기준 {Math.ceil(seconds / 10)}개 vs {Math.ceil(seconds / 15)}개 · 긴 클립은 연결할 구간이 적습니다.</small></article>
    </section>
    <section className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>동일 길이 예상 비용</h2><p>낮은 가격순 · 재생성 0회 · 최대 3개를 골라 아래에서 상세 비교</p></div><label className={styles.search}><span className="sr-only">모델 검색</span><input placeholder="모델 검색" value={query} onChange={event => setQuery(event.target.value)} /></label></div>
      <div className={styles.tableScroll}><table className={styles.table}><caption className="sr-only">{seconds}초 영상 비용 및 {baseline.name} 대비 차이</caption><thead><tr><th scope="col">비교</th><th scope="col">모델 / 가격 출처</th><th scope="col">예상 비용 · 원</th><th scope="col">{baseline.name} 대비</th><th scope="col">클립 / 해상도</th></tr></thead><tbody>{shown.map(row => {
        const delta = row.won - baseline.won;
        return <tr key={row.id} className={selected.includes(row.id) ? styles.selectedRow : undefined}><td><button className={styles.pick} aria-label={`${row.name} 상세 비교 ${selected.includes(row.id) ? "해제" : "선택"}`} aria-pressed={selected.includes(row.id)} disabled={!selected.includes(row.id) && selected.length >= 3} onClick={() => toggle(row.id)}>{selected.includes(row.id) ? "✓" : "+"}</button></td><th scope="row"><strong>{row.name}</strong><small>{row.id === "runway" ? "공식 API" : "힉스필드 · 제공 자료"}</small></th><td><strong className={styles.price}>{money(row.won)}</strong><div className={styles.barTrack} aria-hidden="true"><div style={{ width: `${row.won / maximum * 100}%` }} /></div></td><td><span className={delta < 0 ? styles.lower : delta > 0 ? styles.higher : styles.muted}>{delta === 0 ? "비교 기준" : `${delta < 0 ? "−" : "+"}${money(Math.abs(delta))}`}</span>{delta !== 0 && <small>{Math.abs(delta / baseline.won * 100).toFixed(1)}% {delta < 0 ? "낮음" : "높음"}</small>}</td><td>{row.clips}개 × {row.seconds}초<small>{row.resolution}{row.id !== "runway" ? " · 제공 자료" : " · 설정 기준"}{row.generatedSeconds !== seconds ? ` · ${row.generatedSeconds}초 과금` : ""}</small></td></tr>;
      })}</tbody></table></div>
      {!shown.length && <p className={styles.empty}>검색에 맞는 모델이 없습니다.</p>}
      <p className={styles.footnote}>클립 단위로 올림 계산합니다. 추가 생성·편집·음성·세금·구독료는 제외됩니다. 실제 영상 길이와 청구액은 공급자 조건에 따라 달라집니다.</p>
    </section>
    <section className={styles.panel}>
      <div className={styles.sectionHeading}><div><h2>선택 모델, 무엇이 다른가요?</h2><p>성능 순위가 아닌 비용·제작 조건·연동 준비도를 비교합니다.</p></div><span>{selected.length} / 3개 선택</span></div>
      {details.length ? <div className={styles.detailGrid} style={{ gridTemplateColumns: `repeat(${details.length}, minmax(0, 1fr))` }}>{details.map(row => <article className={styles.detail} key={row.id}><h3>{row.name}</h3><dl>
        <dt>확인 가능한 이점</dt><dd>{row.id === cheapest.id ? "자료상 예상 비용이 가장 낮습니다. " : ""}{row.id === "runway" ? "ASA에 생성 경로가 구현되어 있어 추가 연동 작업이 적습니다. 공급자 채택을 의미하지 않습니다." : row.resolution === "2K" ? "제공 자료상 2K 출력. 다른 720p 후보보다 해상도 조건이 높지만 화질 우위는 미검증입니다." : row.seconds === 15 ? `15초 단위로 ${seconds}초를 ${row.clips}개로 구성해 10초 단위보다 연결 구간이 적습니다.` : "10초 단위 제작 조건입니다. 가격 외의 품질 이점은 아직 검증되지 않았습니다."}</dd>
        <dt>확인할 품질 항목</dt><dd>{row.focus}</dd><dt>ASA 적용에 필요한 일</dt><dd>{row.id === "runway" ? "API 키·잔액·인증 및 실제 생성 확인" : "정확한 API 모델명·요금·참조 이미지 지원 확인 후 생성 경로 구현"}</dd><dt>실제 품질 비교</dt><dd><StatusBadge>동일 씬 테스트 미실시</StatusBadge></dd>
      </dl></article>)}</div> : <p>위 목록에서 비교할 모델을 선택하세요.</p>}
    </section>
    <details className={styles.panel}><summary>연동 준비 상태 · 공급자 선택과 별개</summary><div className={styles.connection}><div><strong>Runway 생성 경로</strong><p>현재 구현된 경로입니다. 사용할 공급자를 확정한 상태는 아닙니다.</p></div><StatusBadge tone={ready ? "success" : "warning"}>{status}</StatusBadge><Button variant="secondary" disabled={loading} onClick={refresh}>상태 새로고침</Button></div><p className={styles.footnote}>서버 설정과 워커 상태만 확인합니다. API 인증·잔액·생성 성공을 보장하지 않습니다.</p></details>
    <footer className={styles.sources}><ExternalLink href={runwayPricingSource}>Runway 공식 API 가격 근거</ExternalLink><p>Runway: 12크레딧/초 × $0.01. 다른 후보: 제공된 힉스필드 가격표의 모델 표기·금액을 사용했습니다. API 제공 여부와 최신 가격은 미확인입니다. 화질 우열은 같은 씬 이미지·프롬프트로 생성해 비교한 뒤 판단해야 합니다.</p></footer>
  </main>;
}
