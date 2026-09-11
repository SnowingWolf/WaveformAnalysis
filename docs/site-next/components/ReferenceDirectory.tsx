import { StaticLink as Link } from "./StaticLink";
import type { AccessorModel, ContextModel, VisualizationModel } from "@/lib/site-model";
import { Icon } from "./icons";

export function ReferenceDirectory({ items, label }: { items: Array<ContextModel | AccessorModel | VisualizationModel>; label: string }) {
  return <div className="reference-directory">{items.map((item) => <Link className="reference-row" href={item.route} key={item.route}><span className="reference-row__icon"><Icon name="api" size={18} /></span><span><strong>{item.name}</strong><small>{item.summary}</small></span><Icon name="arrow" size={17} /></Link>)}<p className="directory-note">{label} 内容由版本化 site-model/v1 提供。</p></div>;
}
