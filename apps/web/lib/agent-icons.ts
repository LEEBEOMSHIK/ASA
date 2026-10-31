export const agentIcons = [
  {id:"bot",label:"로봇",path:"M12 3v3M8 11v2M16 11v2M9 16h6",box:true},
  {id:"pen",label:"대본",path:"m15 4 5 5M4 20l5-1L20 8a2 2 0 0 0-5-5L4 14v6Z"},
  {id:"film",label:"장면",path:"M4 4h16v16H4zM8 4v16M16 4v16M4 9h4M4 15h4M16 9h4M16 15h4"},
  {id:"image",label:"이미지",path:"M3 4h18v16H3zM3 16l5-5 5 5 3-3 5 5M15 8h.01"},
  {id:"palette",label:"디자인",path:"M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h5a4 4 0 0 0 4-4c0-3-4-6-9-6ZM7 10h.01M10 7h.01M15 7h.01M6 14h.01"},
  {id:"mic",label:"음성",path:"M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"},
  {id:"search",label:"검색",path:"M16 16l5 5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z"},
  {id:"shield",label:"검수",path:"m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6"},
  {id:"sparkles",label:"아이디어",path:"m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4M18 4h4"},
  {id:"book",label:"이야기",path:"M12 5v16M12 5C8 2 4 3 2 4v15c4-2 7-1 10 2 3-3 6-4 10-2V4c-2-1-6-2-10 1Z"},
  {id:"code",label:"코드",path:"m8 6-6 6 6 6M16 6l6 6-6 6M14 3l-4 18"},
  {id:"person",label:"캐릭터",path:"M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-3a8 6 0 0 1 16 0v3H4Z"},
] as const;
export type AgentIconId = typeof agentIcons[number]["id"];
