const names: Record<string, string> = {
  marin: "마린", cedar: "시더", alloy: "알로이", ash: "애쉬", ballad: "발라드",
  coral: "코럴", echo: "에코", sage: "세이지", shimmer: "시머", verse: "버스",
};

export function voiceLabel(voice: string): string {
  return names[voice] ? `${names[voice]} (${voice})` : voice;
}
