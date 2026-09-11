import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "WaveformAnalysis 文档", template: "%s · WaveformAnalysis" },
  description: "WaveformAnalysis 离线文档站点",
  icons: { icon: "/assets/waveform-mark.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="zh-CN" suppressHydrationWarning><body><script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem("waveform-docs-theme");if(t==="dark")document.documentElement.dataset.theme="dark"}catch(e){}` }} />{children}</body></html>;
}
