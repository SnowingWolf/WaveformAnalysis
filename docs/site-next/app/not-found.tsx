import { StaticLink as Link } from "@/components/StaticLink";
import { Icon } from "@/components/icons";
import { SiteShell } from "@/components/ServerSiteShell";
import { loadSiteModel } from "@/lib/model";

export default function NotFound() {
  return <SiteShell model={loadSiteModel()} title="页面未找到"><article className="doc-article not-found"><div className="not-found__grid"><span className="not-found__code">404</span><div><h1>页面未找到</h1><p>这个路径不在当前版本的离线文档模型中。</p><Link className="button button--primary" href="/">返回快速开始 <Icon name="arrow" size={17} /></Link></div></div></article></SiteShell>;
}
