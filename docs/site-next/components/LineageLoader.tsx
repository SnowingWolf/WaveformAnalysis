"use client";

import dynamic from "next/dynamic";
import type { LineageModel } from "@/lib/site-model";

const LineageCanvas = dynamic(() => import("./LineageCanvas"), {
  ssr: false,
  loading: () => <div className="lineage-loading-screen" role="status">正在载入处理链画布…</div>,
});

export default function LineageLoader({ initialModel }: { initialModel: LineageModel }) {
  return <LineageCanvas initialModel={initialModel} />;
}
