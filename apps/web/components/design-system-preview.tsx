"use client";

import { useCallback, useEffect, useRef, useState, type ComponentProps } from "react";
import { adminEntries, navigationEntries, productionEntries, startStepsEntry, type CatalogEntry } from "./design-screen-previews";
import {
  ButtonsSpecimen, CheckboxSpecimen, ComboSpecimen, DirectorySpecimen, DisclosureSpecimen, DraftSpecimen,
  HighlightSpecimen, IconsSpecimen, ModalSpecimen, ProgressSpecimen, RequirementsSpecimen, StatusSpecimen,
  SwitchSpecimen, TabsSpecimen, TextAreaSpecimen, TextFieldSpecimen,
} from "./design-system-specimens";
import { ActionIcon, Button, DisclosureIcon, DisclosureSummary, Field } from "./ui";
import { FileUploadPreview } from "./design-interactive-previews";
import { VideoClipSpecs } from "./video-clip-manager";
import styles from "./design-system-preview.module.css";

const themes = [
  { id: "current", label: "앱 테마" },
  { id: "light", label: "밝게" },
  { id: "dark", label: "어둡게" },
] as const;

type PreviewThemeValue = (typeof themes)[number]["id"];

const swatches = [
  ["화면 바탕", "--canvas"], ["카드 바탕", "--surface"], ["본문 글자", "--text"],
  ["기본 강조", "--primary"], ["완료", "--success-bg"], ["주의", "--warning-bg"], ["오류", "--danger-bg"],
];

function ColorsSpecimen() {
  return <ul className={styles.palette} aria-label="기본 색상">
    {swatches.map(([label, token]) => <li key={token}>
      <span aria-hidden="true" className={styles.swatch} style={{ backgroundColor: "var(" + token + ")" }} />
      <span>{label}</span>
    </li>)}
  </ul>;
}

function TypeAndSpacingSpecimen() {
  return <>
    <div className={styles.typeSamples}>
      <strong style={{ fontSize: "var(--font-title)" }}>제목</strong>
      <span>본문</span><small className="muted">도움말</small>
    </div>
    <div className={styles.spacing} aria-label="간격 토큰">
      {[[8, "--space-2"], [16, "--space-4"], [24, "--space-6"]].map(([size, token]) => <span key={token}>
        <span aria-hidden="true" className={styles.measure} style={{ width: "var(" + token + ")" }} />{size}px
      </span>)}
    </div>
  </>;
}

type CatalogGroup = {
  id: string;
  label: string;
  icon: ComponentProps<typeof ActionIcon>["kind"];
  compact?: boolean;
  entries: CatalogEntry[];
};

const groups: CatalogGroup[] = [
  {
    id: "foundations", icon: "palette", label: "기본 스타일·버튼", compact: true, entries: [
      { title: "색상", preview: <ColorsSpecimen />, parts: "바탕·본문·강조색·상태색",
        usage: "정보 위계와 상태의 의미를 일정하게 유지할 때", screen: "스튜디오 공통" },
      { title: "글자·간격", preview: <TypeAndSpacingSpecimen />, parts: "제목·본문·도움말·기본 간격",
        usage: "문구 크기와 영역 사이의 간격을 정할 때", screen: "스튜디오 공통" },
      { title: "동작 버튼", preview: <ButtonsSpecimen />, parts: "기본·보조·비활성·AI 동작",
        usage: "주요 행동과 보조 행동을 구분할 때", screen: "저장·확정·수정·검수" },
      { title: "동작 아이콘", preview: <IconsSpecimen />, parts: "동작별 공통 아이콘과 이름",
        usage: "같은 기능을 어느 화면에서나 알아볼 수 있게 할 때", screen: "스튜디오 공통" },
    ],
  },
  { id: "navigation-patterns", icon: "play", label: "탐색·작업 시작", entries: navigationEntries },
  { id: "production-patterns", icon: "camera", label: "제작·결과 확인", entries: productionEntries },
  {
    id: "work-patterns", icon: "document", label: "작업 화면 구성", entries: [
      startStepsEntry,
      { title: "작업 탭", preview: <TabsSpecimen />, parts: "탭 이름·설명·선택된 영역",
        usage: "같은 작업의 결과와 요청 이력을 오갈 때", screen: "캐릭터·영상·음성 작업 상세" },
      { title: "선택형 작업 카드", href: "/", parts: "씬 이름·상태·선택 표시",
        usage: "여러 씬이나 캐릭터 중 상세를 볼 대상을 고를 때", screen: "씬·캐릭터 이미지 관리" },
      { title: "정보 표", href: "/admin/work-history", parts: "열 이름·행 이름·항목별 값",
        usage: "여러 항목을 같은 기준으로 비교할 때", screen: "작업 관리" },
      { title: "클립 정보 요약", href: "/",
        preview: <VideoClipSpecs modelLabel="WAN 3 · Higgsfield" aspectRatio="9:16"
          clip={{source_start_seconds: 0, source_end_seconds: 5, duration_seconds: 5}} />,
        parts: "영상 모델·계획 구간·길이·화면 비율·시작 기준",
        usage: "클립별 생성 조건을 확인할 때", screen: "클립·영상 생성" },
      { title: "검색·필터·페이지 목록", preview: <DirectorySpecimen />, wide: true,
        parts: "검색창·상태 필터·검색 건수·목록·페이지",
        usage: "많은 항목 중 조건에 맞는 항목을 찾고 상세를 열 때", screen: "사용자·권한 관리 → 역할·메뉴" },
      { title: "접이식 상세", preview: <DisclosureSpecimen />, parts: "제목·펼침 표시·상세 내용",
        usage: "보조 정보나 생성에 사용한 자료를 필요할 때 열어볼 때", screen: "영상 결과의 참고 자료" },
    ],
  },
  { id: "admin-patterns", icon: "settings", label: "운영·비교", entries: adminEntries },
  {
    id: "input-patterns", icon: "edit", label: "입력·선택", compact: true, entries: [
      { title: "입력창·도움말", preview: <TextFieldSpecimen />, parts: "라벨·필수 표시·도움말·오류",
        usage: "값의 형식이나 누락을 바로 알려줄 때", screen: "작업 요청·역할 편집" },
      { title: "검색형 콤보박스", preview: <ComboSpecimen />, parts: "현재 값·검색·선택 목록",
        usage: "여러 값 중 한 항목을 고를 때", screen: "영상 모델·화풍·자료 선택" },
      { title: "체크박스", preview: <CheckboxSpecimen />, parts: "선택 여부·항목 이름",
        usage: "여러 항목을 독립적으로 선택할 때", screen: "선택 생성·권한 관리" },
      { title: "스위치", preview: <SwitchSpecimen />, parts: "켜짐·꺼짐·사용 불가",
        usage: "기능의 사용 여부를 전환할 때", screen: "영상 생성 관리·AI 검수 설정" },
      { title: "긴 텍스트 입력", preview: <TextAreaSpecimen />, parts: "라벨·여러 줄 입력란·도움말",
        usage: "편집 방향이나 수정 요청처럼 문장으로 받는 입력이 필요할 때", screen: "영상 편집 요청·AI 답변 수정" },
      { title: "필수·선택 표시", preview: <RequirementsSpecimen />, parts: "필드 이름·필수 또는 선택 배지",
        usage: "입력해야 할 항목과 생략할 수 있는 항목을 구별할 때", screen: "에이전트 작업 요청 양식" },
      { title: "파일 추가 영역", preview: <FileUploadPreview />, wide: true, href: "/", parts: "드롭 영역·허용 파일·선택 버튼",
        usage: "외부 파일을 작업 자료로 가져올 때", screen: "영상 편집 → 외부 영상 추가" },
    ],
  },
  {
    id: "feedback-patterns", icon: "confirm", label: "상태·검토", entries: [
      { title: "상태 배지", preview: <StatusSpecimen />, parts: "상태별 색상·텍스트",
        usage: "목록이나 상세에서 현재 상태를 짧게 보여줄 때", screen: "작업 목록·영상 검토" },
      { title: "진행 단계", preview: <ProgressSpecimen />, parts: "현재 상태·처리 순서·현재 단계",
        usage: "요청이 어느 단계에서 처리 중인지 안내할 때", screen: "AI 답변 생성 진행" },
      { title: "초안 복원 안내", preview: <DraftSpecimen />, parts: "복원 상태·안내·초기화",
        usage: "이전 입력을 불러온 사실과 다음 행동을 알려줄 때", screen: "에이전트 요청 양식" },
      { title: "모달", preview: <ModalSpecimen />, parts: "제목·본문·닫기와 주요 동작",
        usage: "현재 위치에서 별도 확인이나 선택을 해야 할 때", screen: "자료 가져오기·AI 영상 검수" },
      { title: "검토 하이라이트", preview: <HighlightSpecimen />, wide: true,
        parts: "범례·분류 색상·강조 구절",
        usage: "긴 제작 지시에서 특정 연출만 집중해서 볼 때", screen: "영상 계획 → 영상 제작 지시" },
      { title: "실행 불가 안내", href: "/", parts: "경고·구체적 사유·해결 방향",
        usage: "요청하기 전에 막힌 이유와 해결 방법을 먼저 보여줄 때", screen: "클립·영상 생성" },
      { title: "빈 결과", href: "/characters", parts: "결과 없음 안내·다음 행동",
        usage: "해당 조건의 결과가 없을 때", screen: "보관함·역할 목록" },
    ],
  },
];

const allEntries = groups.flatMap(group => group.entries);
const previewCount = allEntries.filter(entry => entry.preview).length;

function PreviewTheme({ value, onChange }: {
  value: PreviewThemeValue;
  onChange: (theme: PreviewThemeValue) => void;
}) {
  return <fieldset className={styles.theme}>
    <legend>미리보기 테마</legend>
    <div className={styles.themeOptions}>
      {themes.map(option => <label key={option.id}>
        <input type="radio" name="design-preview-theme" value={option.id}
          checked={value === option.id} onChange={() => onChange(option.id)} />
        <span>{option.label}</span>
      </label>)}
    </div>
  </fieldset>;
}

function CatalogLink({ href }: { href: string }) {
  return <a className={styles.sourceLink} href={href}>
    {href === "/" ? "작업 공간 열기" : "적용 화면 열기"} <DisclosureIcon />
  </a>;
}

function ComponentCard({ entry, theme }: { entry: CatalogEntry; theme: PreviewThemeValue }) {
  return <article className={styles.card} data-wide={entry.wide || undefined}
    data-catalog-entry={entry.title} data-preview-source="component">
    <h3>{entry.title}</h3>
    <div className={styles.specimen} aria-label={entry.title + " 미리보기"}
      data-design-preview={theme === "current" ? undefined : theme}>{entry.preview}</div>
    <div className={styles.cardDetails}>
      <details>
        <DisclosureSummary><span className="sr-only">{entry.title} </span>사용 기준</DisclosureSummary>
        <dl className={styles.metadata}>
          <div><dt>구성</dt><dd>{entry.parts}</dd></div>
          <div><dt>사용할 때</dt><dd>{entry.usage}</dd></div>
          <div><dt>적용 화면</dt><dd>{entry.screen}</dd></div>
        </dl>
      </details>
      {entry.href && <CatalogLink href={entry.href} />}
    </div>
  </article>;
}

function CatalogSection({ group, theme }: { group: CatalogGroup; theme: PreviewThemeValue }) {
  const previews = group.entries.filter(entry => entry.preview);
  const references = group.entries.filter(entry => !entry.preview);

  return <section className={styles.group} id={group.id} aria-labelledby={group.id + "-title"}>
    <h2 id={group.id + "-title"}>{group.label}</h2>
    {!!previews.length && <div className={styles.cards} data-compact={group.compact || undefined}>
      {previews.map(entry => <ComponentCard key={entry.title} entry={entry} theme={theme} />)}
    </div>}
    {!!references.length && <div className={styles.referenceGroup}>
      <h3>적용 화면에서 확인</h3>
      <div className={styles.references}>
        {references.map(entry => <article key={entry.title} className={styles.reference}
          data-catalog-entry={entry.title} data-preview-source="link">
          <div><h4>{entry.title}</h4><p>{entry.screen}</p></div>
          {entry.href && <CatalogLink href={entry.href} />}
        </article>)}
      </div>
    </div>}
  </section>;
}

export function DesignSystemPreview() {
  const [theme, setTheme] = useState<PreviewThemeValue>("current");
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const search = useRef<HTMLInputElement>(null);
  const toolbar = useRef<HTMLElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const revealResults = useRef(false);

  const showResults = useCallback(() => {
    const bar = toolbar.current;
    if (!bar) return;
    document.documentElement.style.setProperty("--catalog-filter-height", `${bar.getBoundingClientRect().height}px`);
    results.current?.scrollIntoView({ block: "start", behavior: "instant" });
  }, []);

  const showCompactResults = useCallback(() => {
    if (search.current === document.activeElement &&
      getComputedStyle(document.documentElement).getPropertyValue("--catalog-search-compact").trim() === "1") {
      showResults();
    }
  }, [showResults]);

  useEffect(() => {
    function readCategory() {
      const id = window.location.hash.slice(1);
      if (!id || groups.some(group => group.id === id)) setCategory(id);
    }
    readCategory();
    window.addEventListener("hashchange", readCategory);
    return () => window.removeEventListener("hashchange", readCategory);
  }, []);

  useEffect(() => {
    const bar = toolbar.current;
    if (!bar) return;
    const root = document.documentElement;
    const syncHeight = () => root.style.setProperty("--catalog-filter-height", `${bar.getBoundingClientRect().height}px`);
    const observer = new ResizeObserver(syncHeight);
    observer.observe(bar, { box: "border-box" });
    syncHeight();
    return () => {
      observer.disconnect();
      root.style.removeProperty("--catalog-filter-height");
    };
  }, []);

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    let { height, scale } = viewport;
    function handleResize() {
      if (!viewport) return;
      const shrank = viewport.height < height && viewport.scale === scale;
      ({ height, scale } = viewport);
      if (shrank) showCompactResults();
    }
    viewport.addEventListener("resize", handleResize);
    return () => viewport.removeEventListener("resize", handleResize);
  }, [showCompactResults]);

  useEffect(() => {
    if (!revealResults.current) return;
    revealResults.current = false;
    showResults();
  }, [category, query, showResults]);

  function rememberPinnedPosition() {
    const bar = toolbar.current;
    if (!bar) return;
    const style = getComputedStyle(bar);
    const offset = parseFloat(style.insetBlockStart);
    revealResults.current = style.getPropertyValue("--catalog-search-compact").trim() === "1" ||
      bar.getBoundingClientRect().top <= offset + 1;
  }

  function chooseCategory(id: string) {
    rememberPinnedPosition();
    setCategory(id);
    const url = new URL(window.location.href);
    url.hash = id;
    window.history.replaceState(window.history.state, "", url);
  }

  const activeIcon = groups.find(group => group.id === category)?.icon ?? "composition";
  const normalized = query.trim().toLocaleLowerCase();
  const matches = groups.filter(group => !category || group.id === category).map(group => ({
    ...group, entries: group.entries.filter(entry =>
      [group.label, entry.title, entry.parts, entry.usage, entry.screen].some(text => text.toLocaleLowerCase().includes(normalized))),
  })).filter(group => group.entries.length);
  const count = matches.reduce((sum, group) => sum + group.entries.length, 0);

  return <article className={styles.page} aria-labelledby="design-system-heading">
    <header className={styles.heading}>
      <div>
        <h1 id="design-system-heading">컴포넌트 카탈로그</h1>
        <p className="muted">디자인 토큰과 실제 앱 컴포넌트의 사용 예시</p>
      </div>
      <div className={styles.overview}>
        <dl className={styles.totals}>
          <div><dt>컴포넌트·패턴</dt><dd>{allEntries.length}</dd></div>
          <div><dt>실제 미리보기</dt><dd>{previewCount}</dd></div>
        </dl>
        <PreviewTheme value={theme} onChange={setTheme} />
      </div>
    </header>
    <section ref={toolbar} className={styles.catalogTools} aria-label="카탈로그 검색 및 분류"
      data-catalog-filters="" data-search-active={query ? "" : undefined}>
      <Field id="component-catalog-search" label="컴포넌트 검색">
        {props => <div className={styles.filterControl}>
          <ActionIcon kind="search" />
          <input {...props} ref={search} type="search" placeholder="검색어"
            value={query} onFocus={() => requestAnimationFrame(showCompactResults)} onChange={event => {
              rememberPinnedPosition();
              setQuery(event.target.value);
            }} />
        </div>}
      </Field>
      <div className={styles.compactCategories}>
        <Field id="catalog-category" label="분류">
          {props => <div className={styles.filterControl}>
            <ActionIcon kind={activeIcon} />
            <select {...props} value={category} onChange={event => chooseCategory(event.target.value)}>
              <option value="">전체 분류</option>
              {groups.map(group => <option key={group.id} value={group.id}>{group.label}</option>)}
            </select>
          </div>}
        </Field>
      </div>
      <div role="group" aria-label="컴포넌트 분류" className={styles.categories}>
        <Button variant="secondary" aria-pressed={!category} onClick={() => chooseCategory("")}>
          <ActionIcon kind="composition" /> 전체 분류
        </Button>
        {groups.map(group => <Button key={group.id} variant="secondary"
          aria-pressed={category === group.id} onClick={() => chooseCategory(group.id)}>
          <ActionIcon kind={group.icon} /> {group.label}
        </Button>)}
      </div>
      <p role="status" className={styles.resultCount}>
        {normalized || category ? "검색 결과" : "전체"} <strong>{count}개</strong>
      </p>
    </section>
    <div ref={results} className={styles.results}>
      {count ? <div className={styles.gallery}>
        {matches.map(group => <CatalogSection key={group.id} group={group} theme={theme} />)}
      </div> : <section className={styles.empty} aria-labelledby="catalog-empty-title">
        <h2 id="catalog-empty-title">일치하는 컴포넌트가 없습니다</h2>
        <Button variant="secondary" onClick={() => { setQuery(""); chooseCategory(""); }}>
          <ActionIcon kind="undo" /> 검색·분류 초기화
        </Button>
      </section>}
    </div>
  </article>;
}
