import { SectionHeading } from "@/components/DocPage";
import { ReferenceDirectory } from "@/components/ReferenceDirectory";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export const metadata: Metadata = { title: "可视化", description: "WaveformAnalysis 统计图、波形图与位置二维视图接口参考。" };

export default function VisualizationsPage() {
  const siteModel = loadSiteModel();
  return <SiteShell model={siteModel} title="可视化" toc={[{ id: "overview", label: "可视化参考" }, { id: "directory", label: "绘图接口" }]}><article className="doc-article"><div className="breadcrumbs"><span aria-current="page">可视化</span></div><header className="page-intro"><h1>可视化</h1><p className="page-intro__subtitle">统计图、波形图和位置二维视图的公开绘图接口。</p></header><section id="overview" className="doc-section"><SectionHeading id="overview">可视化参考</SectionHeading><p>可视化函数消费结构化分析产物，保持筛选条件、run_id 与数据来源可追溯。</p></section><section id="directory" className="doc-section"><SectionHeading id="directory">绘图接口</SectionHeading><ReferenceDirectory items={siteModel.visualizations} label="可视化" /></section></article></SiteShell>;
}
import type { Metadata } from "next";
