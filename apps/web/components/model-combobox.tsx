"use client";
import { SelectCombobox } from "./ui";
import type { ModelOption } from "../lib/model-options";
export function ModelCombobox(props:{options:ModelOption[];value:string;onChange:(id:string)=>void;loading:boolean}) {
 return <SelectCombobox {...props} label="모델 선택" caption="최신 세대 우선" hint="최신 세대 · 같은 세대의 일반 모델 우선. 실제 성능 순위는 아닙니다."/>;
}
