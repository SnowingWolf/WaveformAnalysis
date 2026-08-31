import LineageLoader from "@/components/LineageLoader";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function LineagePage() {
  const siteModel = loadSiteModel();
  return <SiteShell model={siteModel} title="插件处理链" fullBleed><LineageLoader initialModel={siteModel.lineage} /></SiteShell>;
}
