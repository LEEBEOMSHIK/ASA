import { Fragment } from "react";

// Render citation links as text + safe anchors; never evaluate model HTML.
export function CitedAnswer({value}: {value: string}) {
  const parts = value.split(/(\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g);
  return <pre className="automation-cited-answer">{parts.map((part,index)=>{
    const match = /^\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
    if (!match) return <Fragment key={index}>{part}</Fragment>;
    try {
      const url = new URL(match[2]);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return part;
      return <a key={index} href={url.href} target="_blank" rel="noopener noreferrer">{match[1]}</a>;
    } catch { return part; }
  })}</pre>;
}
