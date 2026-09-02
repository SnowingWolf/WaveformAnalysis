import LineageLoader from "@/components/LineageLoader";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export const metadata: Metadata = { title: "插件处理链", description: "交互浏览 WaveformAnalysis 插件 DAG、输入输出与上下游依赖。" };

export default function LineagePage() {
  const siteModel = loadSiteModel();
  return <SiteShell model={siteModel} title="插件处理链" fullBleed><LineageLoader initialModel={siteModel.lineage} /></SiteShell>;
}
import type { Metadata } from "next";
