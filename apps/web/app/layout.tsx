import type { Metadata } from "next";
import "./tokens.css";
import "./globals.css";
import { ThemeProvider } from "../components/theme-provider";

export const metadata: Metadata = {
  title: "AI Shorts Studio",
  description: "아이디어를 쇼츠로 만드는 개인 제작 공간",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: `(function(){var p='light';try{p=localStorage.getItem('asa-theme')||'light'}catch(e){}document.documentElement.dataset.theme=p==='dark'||(p==='system'&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light'})();` }} /></head><body><ThemeProvider>{children}</ThemeProvider></body></html>;
}
