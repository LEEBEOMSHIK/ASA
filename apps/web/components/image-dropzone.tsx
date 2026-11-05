"use client";
import { useRef, useState } from "react";
import { Button } from "./ui";

type Props = {
  id: string;
  label: string;
  image: string | null;
  disabled: boolean;
  onFiles: (files: FileList) => void;
};

export function ImageDropzone({ id, label, image, disabled, onFiles }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return <div className={`brand-dropzone ${over ? "is-over" : ""}`}
    onDragOver={event => { event.preventDefault(); setOver(!disabled); }}
    onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setOver(false); }}
    onDrop={event => { event.preventDefault(); setOver(false); if (!disabled) onFiles(event.dataTransfer.files); }}>
    {image && <div className="brand-upload-preview"><img src={image} alt={`${label} 미리보기`}/></div>}
    <strong>{image ? "다른 이미지를 끌어 놓으면 교체됩니다." : "이미지를 여기에 끌어 놓으세요"}</strong>
    <p className="muted" id={`${id}-help`}>PNG · JPG · WebP, 최대 5MB. 저장하면 적용됩니다.</p>
    <input hidden ref={input} id={id} aria-label={label} type="file" disabled={disabled} accept="image/png,image/jpeg,image/webp"
      onChange={event => { if (event.target.files?.length) onFiles(event.target.files); event.target.value = ""; }}/>
    <Button variant="secondary" disabled={disabled} aria-describedby={`${id}-help`} onClick={() => input.current?.click()}>
      {image ? "이미지 변경" : "이미지 선택"}
    </Button>
  </div>;
}
