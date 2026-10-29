export function GraphIcon({kind}:{kind:string}) {
 const paths:Record<string,string>={
  workflow:'M4 3h6v6H4V3Zm10 12h6v6h-6v-6ZM10 6h7v9M7 9v9h7',
  edit:'m4 16 12-12 4 4L8 20H4v-4ZM13 7l4 4',
  clock:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM12 7v5l3 2',
  history:'M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2',
  agent:'M12 3v3M7 6h10a3 3 0 0 1 3 3v10H4V9a3 3 0 0 1 3-3ZM8 11v2m8-2v2m-7 3h6',
  start:'M9 5l11 7-11 7V5Z',end:'M7 3h8l4 4v14H7V3Zm8 0v5h4M10 12h6m-6 4h6',
  ai:'m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  condition:'M6 3v12a4 4 0 0 0 4 4h8M6 7h8a4 4 0 0 0 4-4m-3 13 3 3-3 3',
  repeat:'M4 10a8 8 0 0 1 14-5l2 2m0-5v5h-5M20 14a8 8 0 0 1-14 5l-2-2m0 5v-5h5',
  map:'M4 6h16M4 12h10M4 18h6',tool:'M8 7V3m8 4V3M6 7h12v7a6 6 0 0 1-12 0V7Zm6 13v2',
  settings:'M3 6h4m4 0h10M3 12h10m4 0h4M3 18h4m4 0h10M7 3v6m6 0v6m-6 0v6',
  search:'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z'};
 return <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={paths[kind]||paths.tool}/></svg>;
}
