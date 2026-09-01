"use client";

import { Background, Controls, Handle, MarkerType, MiniMap, Position, ReactFlow, type Edge, type Node, type NodeProps, type ReactFlowInstance } from "@xyflow/react";
import ELK from "elkjs/lib/elk.bundled.js";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { dtypeSummary, edgeHandleMapping, ELK_OPTIONS, visibleGraph, type LineageGraph } from "@/lib/lineage";
import type { LineageModel, LineageNode, LineagePort } from "@/lib/site-model";
import { Icon } from "./icons";

import "@xyflow/react/dist/style.css";

type FlowNodeData = LineageNode & { onSelect: (id: string) => void; active: boolean };
type FlowNode = Node<FlowNodeData, "lineage">;
type FlowEdge = Edge<{ dtype: string; kind: string; color: string }>;

const KIND_COLORS: Record<LineageNode["kind"], { header: string; border: string; tint: string }> = {
  raw: { header: "#d8e9f1", border: "#5d9fb0", tint: "#f5fbfc" },
  record: { header: "#d2eef0", border: "#1292a0", tint: "#f6fcfc" },
  signal: { header: "#d7eee4", border: "#38a47e", tint: "#f6fcf9" },
  peak: { header: "#e7ddf4", border: "#7050ac", tint: "#fcfaff" },
  event: { header: "#d6e3f4", border: "#4c7ebe", tint: "#f8fbff" },
  virtual: { header: "#edf0f2", border: "#9aa5ae", tint: "#fafbfb" },
};

const KIND_LABELS: Record<LineageNode["kind"], string> = { raw: "I/O", record: "Waveform", signal: "Hit", peak: "Peaks", event: "Events", virtual: "Virtual" };

function portRows(ports: LineagePort[], side: "input" | "output", onSelect: (id: string) => void) {
  return ports.map((port, index) => <div className={`lineage-port lineage-port--${side}`} key={port.id} style={{ "--port-top": `${57 + index * 28}px` } as CSSProperties} title={`${port.name} · ${port.dtype}`}>
    {side === "input" && <Handle type="target" position={Position.Left} id={port.id} className="lineage-handle" />}
    {side === "input" && <button type="button" className="lineage-port__label" onClick={(event) => { event.stopPropagation(); onSelect(port.name); }}>{port.name}</button>}
    {side === "output" && <button type="button" className="lineage-port__label" onClick={(event) => event.stopPropagation()}>{port.name}</button>}
    {side === "output" && <Handle type="source" position={Position.Right} id={port.id} className="lineage-handle" />}
  </div>);
}

function LineageNodeView({ data }: NodeProps<FlowNode>) {
  const colors = KIND_COLORS[data.kind];
  const contractDtype = data.outputs[0]?.dtype ?? data.inputs[0]?.dtype ?? "array";
  return <article className={`lineage-node lineage-node--${data.kind}${data.active ? " is-selected" : ""}`} style={{ "--node-border": colors.border, "--node-header": colors.header, "--node-tint": colors.tint } as CSSProperties} onClick={() => data.onSelect(data.id)}>
    <header><strong>{data.label}</strong><span>{data.pluginClass}</span></header>
    <div className="lineage-node__ports">{portRows(data.inputs, "input", data.onSelect)}{portRows(data.outputs, "output", data.onSelect)}</div>
    <footer title={contractDtype}>{dtypeSummary(contractDtype)}</footer>
  </article>;
}

const nodeTypes = { lineage: LineageNodeView };

function nodeHeight(node: LineageNode) { return Math.max(128, 57 + Math.max(node.inputs.length, node.outputs.length, 1) * 28 + 27); }

function colorForNode(node: LineageNode | undefined) { return node ? KIND_COLORS[node.kind].border : "#1995a2"; }

function buildFlow(graph: LineageGraph, selected: string, onSelect: (id: string) => void) {
  const nodes: FlowNode[] = graph.nodes.map((node, index) => ({
    id: node.id,
    type: "lineage",
    position: { x: (index % 5) * 260, y: Math.floor(index / 5) * 210 },
    data: { ...node, onSelect, active: node.id === selected },
    style: { width: 198, height: nodeHeight(node) },
  }));
  const nodeMap = new Map(graph.nodes.map((node) => [node.id, node]));
  const edges: FlowEdge[] = graph.edges.map((edge) => ({
    id: edge.id,
    ...edgeHandleMapping(edge),
    type: "smoothstep",
    data: { dtype: edge.dtype, kind: edge.kind, color: colorForNode(nodeMap.get(edge.source)) },
    style: { stroke: colorForNode(nodeMap.get(edge.source)), strokeWidth: edge.kind === "main" ? 2.8 : 2.1 },
    markerEnd: { type: MarkerType.ArrowClosed, color: colorForNode(nodeMap.get(edge.source)) },
  }));
  return { nodes, edges };
}

async function fetchLineage(): Promise<LineageModel> {
  const response = await fetch("/api/lineage", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`lineage API ${response.status}`);
  const payload: unknown = await response.json();
  if (typeof payload !== "object" || payload === null) throw new Error("lineage API returned a non-object");
  const maybe = payload as { lineage?: LineageModel; nodes?: LineageModel["nodes"] };
  if (maybe.lineage) return maybe.lineage;
  if (maybe.nodes) return payload as LineageModel;
  throw new Error("lineage API payload has no lineage");
}

export default function LineageCanvas({ initialModel }: { initialModel: LineageModel }) {
  const [model, setModel] = useState(initialModel);
  const [source, setSource] = useState<"api" | "static fallback">("static fallback");
  const [view, setView] = useState<"overview" | "full">("overview");
  const [selected, setSelected] = useState("records");
  const [query, setQuery] = useState("");
  const [showVirtual, setShowVirtual] = useState(true);
  const [flow, setFlow] = useState<{ nodes: FlowNode[]; edges: FlowEdge[] }>(() => buildFlow(visibleGraph(initialModel, "overview"), "records", setSelected));
  const [layoutPending, setLayoutPending] = useState(true);
  const [instance, setInstance] = useState<ReactFlowInstance<FlowNode, FlowEdge> | null>(null);
  const layoutRevision = useRef(0);

  useEffect(() => {
    let cancelled = false;
    fetchLineage().then((next) => { if (!cancelled) { setModel(next); setSource("api"); } }).catch(() => { if (!cancelled) setSource("static fallback"); });
    return () => { cancelled = true; };
  }, []);

  const displayModel = useMemo(() => {
    if (showVirtual) return model;
    const ids = new Set(model.nodes.filter((node) => node.kind !== "virtual").map((node) => node.id));
    return { ...model, nodes: model.nodes.filter((node) => ids.has(node.id)), edges: model.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)), views: { ...model.views, overview: model.views.overview.filter((id) => ids.has(id)), full: model.views.full.filter((id) => ids.has(id)) } };
  }, [model, showVirtual]);

  const selectedNode = displayModel.nodes.find((node) => node.id === selected) ?? displayModel.nodes[0];
  const selectedConsumers = selectedNode ? model.edges.filter((edge) => edge.source === selectedNode.id).map((edge) => edge.target).filter((id, index, values) => values.indexOf(id) === index) : [];
  // Selection drives the inspector/highlight only.  A graph focus is an
  // explicit navigation mode, so changing the selected node must not shrink
  // the Overview or Full view to its immediate neighborhood.
  const graph = useMemo(() => visibleGraph(displayModel, view), [displayModel, view]);
  const filteredSidebar = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return displayModel.nodes.filter((node) => !normalized || `${node.id} ${node.label} ${node.pluginClass}`.toLocaleLowerCase().includes(normalized));
  }, [displayModel.nodes, query]);

  const relayout = useCallback(async (nextGraph: LineageGraph) => {
    const revision = ++layoutRevision.current;
    setLayoutPending(true);
    const elk = new ELK();
    const result = await elk.layout({
      id: "root",
      layoutOptions: ELK_OPTIONS,
      children: nextGraph.nodes.map((node) => ({ id: node.id, width: 198, height: nodeHeight(node), layoutOptions: { "org.eclipse.elk.portConstraints": "FIXED_ORDER" }, ports: [...node.inputs, ...node.outputs].map((port) => ({ id: port.id, width: 8, height: 8, layoutOptions: { "org.eclipse.elk.port.side": port.side === "input" ? "WEST" : "EAST" } })) })),
      edges: nextGraph.edges.map((edge) => ({ id: edge.id, sources: [edge.sourcePort], targets: [edge.targetPort] })),
    });
    if (revision !== layoutRevision.current) return;
    const positions = new Map((result.children ?? []).map((node) => [node.id, { x: node.x ?? 0, y: node.y ?? 0 }]));
    setFlow({
      nodes: buildFlow(nextGraph, selected, setSelected).nodes.map((node) => ({ ...node, position: positions.get(node.id) ?? node.position })),
      edges: buildFlow(nextGraph, selected, setSelected).edges,
    });
    setLayoutPending(false);
  }, [selected]);

  useEffect(() => { void relayout(graph); }, [graph, relayout]);

  // React Flow measures freshly committed nodes asynchronously.  Fitting from
  // the ELK promise callback can therefore run against the previous DOM and
  // leave a newly selected view outside the viewport.  Wait for the state
  // commit and two animation frames so React Flow has measured the new bounds.
  useEffect(() => {
    if (layoutPending || !instance || !flow.nodes.length) return;
    let cancelled = false;
    let secondFrame = 0;
    const firstFrame = window.requestAnimationFrame(() => {
      secondFrame = window.requestAnimationFrame(() => {
        if (!cancelled) instance.fitView({ padding: .18, duration: 300 });
      });
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(firstFrame);
      if (secondFrame) window.cancelAnimationFrame(secondFrame);
    };
  }, [flow.nodes, instance, layoutPending]);

  const selectNode = useCallback((id: string) => setSelected(id), []);
  const flowSelection = useMemo(() => ({ nodes: flow.nodes.map((node) => ({ ...node, data: { ...node.data, onSelect: selectNode, active: node.id === selected } })) }), [flow.nodes, selectNode, selected]);

  return <section className="lineage-workbench" aria-label="插件处理链浏览器">
    <aside className="lineage-sidebar"><div className="lineage-sidebar__head"><button className="lineage-collapse" type="button" aria-label="收起插件筛选栏"><Icon name="chevron" size={17} /></button><strong>插件处理链</strong><span className="lineage-count">{displayModel.nodes.length}</span></div><label className="lineage-filter"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="过滤插件..." aria-label="过滤插件" /></label><div className="lineage-groups">{(["raw", "record", "signal", "peak", "event"] as const).map((kind) => { const items = filteredSidebar.filter((node) => node.kind === kind); if (!items.length) return null; return <section key={kind}><div className="lineage-group__title"><Icon name="folder" size={15} /><span>{KIND_LABELS[kind]}</span><small>{items.length}</small><Icon name="chevron" size={14} /></div>{items.map((node) => { const outputDtype = node.outputs[0]?.dtype ?? "array"; return <button className={`lineage-sidebar__item${node.id === selected ? " is-active" : ""}`} type="button" key={node.id} onClick={() => selectNode(node.id)}><span className="lineage-dot" style={{ background: colorForNode(node) }} /><span className="lineage-sidebar__name">{node.label}</span><small title={outputDtype}>{dtypeSummary(outputDtype)}</small></button>; })}</section>; })}</div><div className="lineage-sidebar__status"><span className="status-dot" />{displayModel.nodes.length} plugins · {source}</div></aside>
    <div className="lineage-canvas-area"><div className="lineage-toolbar"><h1>插件处理链</h1><label className="lineage-search"><Icon name="search" size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索插件或产物" aria-label="搜索插件或产物" /><kbd>⌘ K</kbd></label><div className="lineage-view-tabs" role="tablist"><button type="button" role="tab" aria-selected={view === "overview"} className={view === "overview" ? "is-active" : ""} onClick={() => setView("overview")}>Overview</button><button type="button" role="tab" aria-selected={view === "full"} className={view === "full" ? "is-active" : ""} onClick={() => setView("full")}>Full</button></div><label className="virtual-toggle"><span>显示虚拟节点</span><input type="checkbox" checked={showVirtual} onChange={(event) => setShowVirtual(event.target.checked)} /><i /></label><button className="lineage-tool-button" type="button" onClick={() => instance?.fitView({ padding: .18, duration: 300 })}><Icon name="fit" size={16} />适应画布</button><button className="lineage-tool-button" type="button" onClick={() => { setView("overview"); setSelected("records"); }}><Icon name="refresh" size={16} />重置</button></div><div className="lineage-canvas" aria-label="处理链画布"><ReactFlow nodes={flowSelection.nodes} edges={flow.edges} nodeTypes={nodeTypes} onInit={setInstance} onNodeClick={(_, node) => selectNode(node.id)} fitView fitViewOptions={{ padding: .16 }} minZoom={.15} maxZoom={1.45} nodesDraggable nodesConnectable={false} elementsSelectable proOptions={{ hideAttribution: true }}><Background color="#dfe6e9" gap={18} size={1} /><MiniMap position="bottom-left" nodeColor={(node) => colorForNode(displayModel.nodes.find((entry) => entry.id === node.id))} maskColor="rgb(255 255 255 / 72%)" /><Controls position="bottom-right" showInteractive={false} /></ReactFlow>{layoutPending && <span className="lineage-loading">正在布局…</span>}</div></div>
    <aside className="lineage-inspector" aria-label="插件详情">{selectedNode ? <><div className="inspector-head"><div><h2>{selectedNode.label}</h2><p>{selectedNode.pluginClass}</p></div><button className="icon-button" type="button" aria-label="关闭插件详情" onClick={() => setSelected("")}><Icon name="close" size={18} /></button></div><dl className="inspector-meta"><div><dt>类</dt><dd>{selectedNode.pluginClass}</dd></div><div><dt>版本</dt><dd>{selectedNode.version ?? "—"}</dd></div><div><dt>状态</dt><dd><span className="status-dot" />已解析</dd></div><div><dt>位置</dt><dd>{Math.max(1, displayModel.nodes.findIndex((node) => node.id === selectedNode.id) + 1)} / {displayModel.nodes.length}</dd></div></dl><div className="inspector-section"><h3>契约</h3><div className="inspector-contract"><span>输入</span><strong>{selectedNode.inputs.map((port) => port.name).join(", ") || "—"}</strong><span>输出</span><strong>{selectedNode.outputs.map((port) => port.name).join(", ") || "—"}</strong></div></div><div className="inspector-section"><h3>输入 <em>{selectedNode.inputs.length}</em></h3>{selectedNode.inputs.map((port) => <div className="inspector-port" key={port.id}><span className="lineage-dot" style={{ background: colorForNode(selectedNode) }} /><strong>{port.name}</strong><small title={port.dtype}>{port.dtype}</small></div>)}</div><div className="inspector-section"><h3>输出 <em>{selectedNode.outputs.length}</em></h3>{selectedNode.outputs.map((port) => <div className="inspector-port" key={port.id}><span className="lineage-dot" style={{ background: colorForNode(selectedNode) }} /><strong>{port.name}</strong><small title={port.dtype}>{port.dtype}</small></div>)}</div><div className="inspector-section inspector-consumers"><h3>下游 <em>{selectedConsumers.length}</em></h3>{selectedConsumers.map((consumer) => <span key={consumer}><span className="lineage-dot" style={{ background: colorForNode(displayModel.nodes.find((node) => node.id === consumer)) }} />{consumer}</span>)}</div></> : <div className="inspector-empty">选择一个插件查看契约。</div>}</aside>
  </section>;
}
