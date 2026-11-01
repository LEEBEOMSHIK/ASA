import { Fragment } from "react";
import { AnswerView } from "./agent-answer";

// Deliberately render only text, headings, lists and emphasis. Model HTML stays text.
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) => part.startsWith("**") && part.endsWith("**")
    ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>);
}
export function ReviewAnswer({ value }: { value: unknown }) {
  if (typeof value !== "string") return <AnswerView value={value}/>;
  const lines = value.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i].trim();
    if (!line) { i++; continue; }
    const heading = /^#{1,6}\s+(.+)$/.exec(line);
    if (heading) { blocks.push(<h5 key={i}>{inline(heading[1])}</h5>); i++; continue; }
    const ordered = /^\d+[.)]\s+/.test(line);
    if (ordered || /^[-*+]\s+/.test(line)) {
      const start = i, items = [], pattern = ordered ? /^\d+[.)]\s+/ : /^[-*+]\s+/;
      while (i < lines.length && pattern.test(lines[i].trim())) {
        items.push(<li key={i}>{inline(lines[i++].trim().replace(pattern, ""))}</li>);
      }
      blocks.push(ordered ? <ol key={start}>{items}</ol> : <ul key={start}>{items}</ul>);
      continue;
    }
    const start = i, paragraph = [lines[i++]];
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|[-*+]\s|\d+[.)]\s)/.test(lines[i].trim())) paragraph.push(lines[i++]);
    blocks.push(<p key={start}>{inline(paragraph.join("\n"))}</p>);
  }
  return <div className="review-answer">{blocks}</div>;
}
