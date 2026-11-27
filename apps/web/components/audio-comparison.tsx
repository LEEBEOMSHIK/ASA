"use client";

import { useEffect, useRef, useState, type RefCallback } from "react";
import { audioComparisonModels } from "../lib/audio-comparison";
import { api } from "../lib/registry";
import { useAccess } from "./access-provider";
import { ExternalLink, Field, StatusBadge } from "./ui";
import styles from "./audio-comparison.module.css";

type AudioCatalog = {
  models: Record<string, { model: string }>;
  generation_enabled: boolean;
};
type AudioAsset = { id: string; name: string; duration: number };
type CatalogState = AudioCatalog | "loading" | "error";
type AssetState = AudioAsset[] | "loading" | "error";

function ModelStatus({ id, catalog }: { id: string; catalog: CatalogState }) {
  if (catalog === "loading") return <StatusBadge>설정 확인 중</StatusBadge>;
  if (catalog === "error") return <StatusBadge tone="warning">설정 확인 불가</StatusBadge>;
  if (!Object.values(catalog.models).some(model => model.model === id)) {
    return <StatusBadge>앱 미연동</StatusBadge>;
  }
  return catalog.generation_enabled
    ? <StatusBadge tone="success">앱에 설정됨</StatusBadge>
    : <StatusBadge tone="warning">음성 생성 사용 불가</StatusBadge>;
}

function SamplePlayer({ asset, label, bind, onPlay }: {
  asset: AudioAsset;
  label: string;
  bind: RefCallback<HTMLAudioElement>;
  onPlay: () => void;
}) {
  const [source, setSource] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const request = new AbortController();
    let mediaUrl: string | undefined;
    fetch(`/api/v1/audio/assets/${encodeURIComponent(asset.id)}/media`, {
      signal: request.signal,
      credentials: "same-origin",
    }).then(response => {
      if (!response.ok) throw new Error("audio_asset_unavailable");
      return response.blob();
    }).then(media => {
      if (request.signal.aborted) return;
      mediaUrl = URL.createObjectURL(media);
      setSource(mediaUrl);
    }).catch(() => {
      if (!request.signal.aborted) setFailed(true);
    });
    return () => {
      request.abort();
      if (mediaUrl) URL.revokeObjectURL(mediaUrl);
    };
  }, [asset.id]);

  if (failed) return <p role="alert" className="field-error">음원을 재생할 수 없습니다.</p>;
  if (!source) return <p role="status" className="muted">음원 재생을 준비하는 중입니다…</p>;
  return <audio ref={bind} controls preload="metadata" src={source}
    aria-label={`${label} 재생 · ${asset.name}`} onPlay={onPlay} onError={() => setFailed(true)} />;
}

export function AudioComparison({ initialLeft, initialRight }: {
  initialLeft: string;
  initialRight: string;
}) {
  const access = useAccess();
  const canReadAudio = access.can("home.view") || access.can("characters.view");
  const [catalog, setCatalog] = useState<CatalogState>("loading");
  const [assets, setAssets] = useState<AssetState>("loading");
  const [selected, setSelected] = useState([initialLeft, initialRight]);
  const players = useRef<(HTMLAudioElement | null)[]>([]);

  useEffect(() => {
    let active = true;
    api<AudioCatalog>("/audio/catalog")
      .then(value => { if (active) setCatalog(value); })
      .catch(() => { if (active) setCatalog("error"); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!canReadAudio) return;
    let active = true;
    api<AudioAsset[]>("/audio/assets")
      .then(value => { if (active) setAssets(value); })
      .catch(() => { if (active) setAssets("error"); });
    return () => { active = false; };
  }, [canReadAudio]);

  return <div className={styles.page}>
    <header className={styles.header}>
      <h1>음성 AI 비교</h1>
      <p>한국어 내레이션과 캐릭터 대사에 사용할 모델을 비교하세요.</p>
    </header>

    <section className={styles.section} aria-labelledby="audio-model-comparison">
      <h2 id="audio-model-comparison">모델별 기능과 연동</h2>
      <div className={styles.grid}>
        {audioComparisonModels.map(model => <article className={styles.card} key={model.id}>
          <header className={styles.modelHeader}>
            <div><p className={styles.provider}>{model.provider}</p><h3>{model.name}</h3></div>
            <ModelStatus id={model.id} catalog={catalog} />
          </header>
          <dl className={styles.specs}>
            <div><dt>언어·화자</dt><dd>{model.voices}</dd></div>
            <div><dt>연기 제어</dt><dd>{model.delivery}</dd></div>
            <div><dt>과금 기준</dt><dd>{model.billing}</dd></div>
          </dl>
          <div className={styles.links}>
            <ExternalLink href={model.docs}>공식 기능 안내</ExternalLink>
            <ExternalLink href={model.price}>공식 요금</ExternalLink>
          </div>
        </article>)}
      </div>
    </section>

    <section className={styles.samples} aria-labelledby="audio-sample-comparison">
      <header className={styles.header}>
        <h2 id="audio-sample-comparison">음원 비교 듣기</h2>
        <p>같은 대사로 만든 샘플을 골라 발음, 감정, 화자 구분을 비교하세요.</p>
      </header>
      {!access.ready ?
        <p role="status" className="muted">음원을 불러오는 중입니다…</p>
        : !canReadAudio ?
          <p className="muted">보관함 음원을 들으려면 작업 공간 또는 보관함 조회 권한이 필요합니다.</p>
        : assets === "loading" ?
          <p role="status" className="muted">음원을 불러오는 중입니다…</p>
        : assets === "error" ?
          <p role="alert" className="field-error">저장된 음원을 불러오지 못했습니다.</p>
        : assets.length === 0 ?
          <p className="muted">비교할 수 있는 저장 음원이 없습니다.</p>
        : <div className={styles.grid}>
          {["A", "B"].map((slot, index) => {
            const asset = assets.find(item => item.id === selected[index]);
            const label = `비교 음원 ${slot}`;
            return <div key={slot} className={styles.player}>
              <Field id={`comparison-sample-${slot}`} label={label}>
                {props => <select {...props} title={asset?.name} value={asset?.id ?? ""} onChange={event => {
                  const value = event.target.value;
                  setSelected(previous => previous.map((id, position) => position === index ? value : id));
                }}>
                  <option value="">저장 음원 선택</option>
                  {assets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>}
              </Field>
              {asset && <SamplePlayer key={asset.id} asset={asset} label={label}
                bind={element => { players.current[index] = element; }}
                onPlay={() => players.current.forEach((player, position) => {
                  if (position !== index) player?.pause();
                })} />}
            </div>;
          })}
        </div>}
    </section>
  </div>;
}
