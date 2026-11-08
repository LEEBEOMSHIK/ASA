export const navigationItems: {id:string;href:string;label:string;icon:string;admin?:boolean}[] = [
  {id:"home",href:"/",label:"작업 공간",icon:"work"},
  {id:"automations",href:"/automations",label:"자동화 빌더",icon:"flow"},
  {id:"agents",href:"/agents",label:"에이전트",icon:"agent"},
  {id:"characters",href:"/characters",label:"보관함",icon:"archive"},
  {id:"tools",href:"/tools",label:"도구 라이브러리",icon:"tools"},
  {id:"video-comparison",href:"/video-comparison",label:"영상 AI 비교",icon:"comparison"},
  {id:"admin-agents",href:"/admin/agents",label:"에이전트 관리",icon:"agent-settings",admin:true},
  {id:"work-history",href:"/admin/work-history",label:"작업 관리",icon:"history",admin:true},
  {id:"models",href:"/models",label:"AI 모델 관리",icon:"model",admin:true},
  {id:"monitoring",href:"/monitoring",label:"AI 사용량·비용",icon:"usage",admin:true},
  {id:"branding",href:"/admin/branding",label:"브랜드 설정",icon:"brand",admin:true},
];
export const navigationColors = [
  {id:"red",label:"빨강"},{id:"orange",label:"주황"},{id:"green",label:"초록"},
  {id:"blue",label:"파랑"},{id:"purple",label:"보라"},{id:"pink",label:"분홍"},
] as const;
export type NavigationColor = typeof navigationColors[number]["id"] | `#${string}`;
export type NavigationColorValue = {color:NavigationColor|null;revision:number};
export type NavigationColorItems = Record<string,NavigationColorValue>;
