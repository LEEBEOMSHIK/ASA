export function videoLinkLabel(value: string): string | null {
  try {
    const url = new URL(value.trim());
    if (value.trim().length > 2048 || url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
    const parts = url.pathname.replace(/^\/+|\/+$/g, "").split("/");
    let id = "";
    if (url.hostname === "youtu.be" && parts.length === 1) id = parts[0];
    if (["youtube.com", "www.youtube.com", "m.youtube.com"].includes(url.hostname)) {
      if (url.pathname === "/watch") id = url.searchParams.get("v") || "";
      else if (parts.length === 2 && ["shorts", "embed"].includes(parts[0])) id = parts[1];
    }
    if (/^[A-Za-z0-9_-]{11}$/.test(id)) return "YouTube 영상 링크";
    if (["instagram.com", "www.instagram.com"].includes(url.hostname) && parts.length === 2 && ["reel", "reels"].includes(parts[0]) && /^[A-Za-z0-9_-]{3,100}$/.test(parts[1])) return "Instagram Reels 링크";
  } catch { /* Incomplete addresses are validated while editing. */ }
  return null;
}

export function pendingVideoUrl(value: string): string | null {
  try { const data = JSON.parse(value); return data?.format === "asa_video_link_pending" && typeof data.url === "string" ? data.url : null; }
  catch { return null; }
}
