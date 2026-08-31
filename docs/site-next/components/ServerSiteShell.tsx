import type { ReactNode } from "react";
import type { SiteModel } from "@/lib/site-model";
import { siteShellModel } from "@/lib/search";
import { SiteShell as ClientSiteShell, type TocItem } from "./SiteShell";

/** Server boundary that strips large guide bodies and schemas from shared client props. */
export function SiteShell({
  model,
  children,
  toc = [],
  title = "文档",
  compactNav = false,
  fullBleed = false,
}: {
  model: SiteModel;
  children: ReactNode;
  toc?: TocItem[];
  title?: string;
  compactNav?: boolean;
  fullBleed?: boolean;
}) {
  return (
    <ClientSiteShell
      model={siteShellModel(model)}
      toc={toc}
      title={title}
      compactNav={compactNav}
      fullBleed={fullBleed}
    >
      {children}
    </ClientSiteShell>
  );
}
