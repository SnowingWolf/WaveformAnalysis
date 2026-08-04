import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createRoot } from "react-dom/client";
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  PanOnScrollMode,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import ELK from "elkjs/lib/elk.bundled.js";
import {
  edgeHandleMapping,
  invalidConnections,
  LINEAGE_LAYOUT_OPTIONS,
  normalizeView,
  orthogonalPoints,
  orthogonalPath,
  withoutVirtualNodes,
  visibleGraph,
  type Graph,
  type GraphEdge,
  type GraphNodeData,
  type Point,
  type PortData,
} from "./lineage";
import "./site.css";

const elk = new ELK();
type InputSourceAction = (
  event: React.MouseEvent<HTMLButtonElement>, sourceId: string, action: "preview" | "pin",
) => void;
type FlowNodeData = GraphNodeData & { onInputSourceAction?: InputSourceAction };
type FlowNode = Node<FlowNodeData, "dag">;
type FlowEdgeData = Record<string, unknown> & { orthogonalPath: string | null; points: Point[] | null; dtype: string; color: string };

function Port({ port, side, onInputSourceAction }: { port: PortData; side: "in" | "out"; onInputSourceAction?: InputSourceAction }) {
  const [active, setActive] = useState(false);
  const top = NODE_HEADER_HEIGHT + NODE_PORT_PADDING + port.index * PORT_ROW_HEIGHT;
  return <div className={`wfa-flow-port wfa-flow-port--${side}`} style={{ top }} title={side === "out" ? `${port.name}: ${port.dtype}` : port.dtype}>
    {side === "in" && <Handle className="wfa-flow-port-handle" type="target" id={port.id} position={Position.Left} />}
    {side === "in" && <button className={`wfa-flow-port-dot ${active ? "is-active" : ""}`} type="button" aria-label={`定位来源插件：${port.name}`} onClick={(event) => { event.stopPropagation(); setActive((value) => !value); onInputSourceAction?.(event, port.name, "pin"); }} style={{ "--port-color": port.color } as CSSProperties} />}
    {side === "in" && <button className="wfa-flow-port-name" type="button" onClick={(event) => { event.stopPropagation(); onInputSourceAction?.(event, port.name, "preview"); }}>{port.name}</button>}
    {side === "out" && <button className={`wfa-flow-port-dot ${active ? "is-active" : ""}`} type="button" aria-label={`输出：${port.name}`} onClick={(event) => { event.stopPropagation(); setActive((value) => !value); }} style={{ "--port-color": port.color } as CSSProperties} />}
    {side === "out" && <Handle className="wfa-flow-port-handle" type="source" id={port.id} position={Position.Right} />}
  </div>;
}

const NODE_HEADER_HEIGHT = 58;
const NODE_PORT_PADDING = 8;
const PORT_ROW_HEIGHT = 28;
const PORT_DOT_SIZE = 10;
const MIN_NODE_WIDTH = 172;
const MIN_NODE_HEIGHT = 116;
const RECORDS_MIN_NODE_HEIGHT = 136;
// This is only an interaction guard.  Initial zoom always comes from fitView
// and therefore follows the actual Overview or Full DAG bounds.
const MIN_CANVAS_ZOOM = 0.1;

function nodeDimensions(data: GraphNodeData) {
  const titleWidth = Math.max(data.id.length, data.pluginClass.length) * 9.8 + 32;
  const inputWidth = Math.max(0, ...data.in_ports.map((port) => port.name.length)) * 7.1 + 34;
  return {
    width: Math.max(MIN_NODE_WIDTH, Math.ceil(titleWidth), Math.ceil(inputWidth + 26)),
    height: Math.max(
      data.id === "records" ? RECORDS_MIN_NODE_HEIGHT : MIN_NODE_HEIGHT,
      NODE_HEADER_HEIGHT + NODE_PORT_PADDING * 2
        + Math.max(data.in_ports.length, data.out_ports.length, 1) * PORT_ROW_HEIGHT,
    ),
  };
}

function elkPort(port: PortData, nodeWidth: number) {
  return {
    id: port.id,
    width: PORT_DOT_SIZE,
    height: PORT_DOT_SIZE,
    x: port.kind === "in" ? 0 : nodeWidth - PORT_DOT_SIZE,
    y: NODE_HEADER_HEIGHT + NODE_PORT_PADDING + port.index * PORT_ROW_HEIGHT
      + (PORT_ROW_HEIGHT - PORT_DOT_SIZE) / 2,
    layoutOptions: {
      "org.eclipse.elk.port.side": port.kind === "in" ? "WEST" : "EAST",
    },
  };
}

function DagNode({ data }: NodeProps<FlowNode>) {
  const style = {
    "--node-background": data.colors.background,
    "--node-border": data.colors.border,
    "--node-header": data.colors.header,
  } as CSSProperties;
  return <article className={`wfa-flow-node wfa-flow-node--${data.kind}${data.isLineageVirtual ? " is-lineage-virtual" : ""}`} style={style}>
    <header><strong>{data.id}</strong><span>{data.pluginClass}</span></header>
    <div className="wfa-flow-ports">
      <div>{data.in_ports.map((port) => <Port key={port.id} port={port} side="in" onInputSourceAction={data.onInputSourceAction} />)}</div>
      <div>{data.out_ports.map((port) => <Port key={port.id} port={port} side="out" />)}</div>
    </div>
  </article>;
}

const nodeTypes = { dag: DagNode };

function WireLayer({
  edges,
  viewport,
}: {
  edges: Edge<FlowEdgeData>[];
  viewport: { x: number; y: number; zoom: number };
}) {
  const markerId = (color: string) => `wfa-flow-arrow-${color.replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const markerColors = [...new Set(edges.map((edge) => edge.data?.color ?? "#526a5f"))];
  const segments = new Map<string, {
    id: string;
    path: string;
    color: string;
    className: string;
    style: CSSProperties;
    isTerminal: boolean;
  }>();
  edges.forEach((edge) => {
    const points = edge.data?.points;
    if (!points || points.length < 2) return;
    points.slice(1).forEach((point, index) => {
      const start = points[index];
      const isTerminal = index === points.length - 2;
      // Edges sharing a source port form one physical LabVIEW-style trunk.
      // Draw a shared segment once, then let only the diverging segments fan out.
      const key = [edge.sourceHandle, start.x, start.y, point.x, point.y].join(":");
      const existing = segments.get(key);
      if (existing) {
        existing.isTerminal ||= isTerminal;
        return;
      }
      segments.set(key, {
        id: `${edge.id}::${index}`,
        path: `M ${start.x} ${start.y} L ${point.x} ${point.y}`,
        color: edge.data?.color ?? "#526a5f",
        className: edge.className ?? "",
        style: edge.style ?? {},
        isTerminal,
      });
    });
  });
  const wireSegments = [...segments.values()];
  return <svg className="wfa-flow-wires" aria-hidden="true">
    <defs>
      {markerColors.map((color) => <marker key={color} id={markerId(color)} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill={color} />
      </marker>)}
    </defs>
    <g transform={`translate(${viewport.x} ${viewport.y}) scale(${viewport.zoom})`}>
      {/* Paint all halos first so a later branch cannot erase the common,
          colored portion of an earlier branch. */}
      <g className="wfa-flow-wire-halos">
        {wireSegments.map((segment) => <path key={segment.id} className="wfa-flow-wire-halo" d={segment.path} />)}
      </g>
      <g className="wfa-flow-wire-strokes">
        {wireSegments.map((segment) => <path
          key={segment.id}
          className={`wfa-flow-wire ${segment.className}`}
          d={segment.path}
          markerEnd={segment.isTerminal ? `url(#${markerId(segment.color)})` : undefined}
          style={segment.style}
        />)}
      </g>
    </g>
  </svg>;
}

function seedNodes(graph: Graph, view: string, focus: string, onInputSourceAction?: InputSourceAction): FlowNode[] {
  return visibleGraph(graph, view, focus).nodes.map((node, index) => ({
    id: node.data.id,
    position: { x: (index % 5) * 280, y: Math.floor(index / 5) * 160 },
    data: { ...node.data, onInputSourceAction },
    type: "dag",
    style: nodeDimensions(node.data),
  }));
}

async function layout(
  graph: Graph,
  view: string,
  focus: string,
  measured: Map<string, { width: number; height: number }>,
  onInputSourceAction?: InputSourceAction,
) {
  const visible = visibleGraph(graph, view, focus);
  const result = await elk.layout({
    id: "root",
    layoutOptions: LINEAGE_LAYOUT_OPTIONS,
    children: visible.nodes.map((node) => {
      const size = measured.get(node.data.id) ?? nodeDimensions(node.data);
      return {
        id: node.data.id,
        width: size.width,
        height: size.height,
        layoutOptions: { "org.eclipse.elk.portConstraints": "FIXED_POS" },
        ports: [
          ...node.data.in_ports.map((port) => elkPort(port, size.width)),
          ...node.data.out_ports.map((port) => elkPort(port, size.width)),
        ],
      };
    }),
    edges: visible.edges.map((edge) => ({
      id: edge.data.id,
      sources: [edge.data.source_port_id],
      targets: [edge.data.target_port_id],
    })),
  });
  const positions = new Map((result.children ?? []).map((node) => [node.id, node]));
  const sections = new Map(
    (result.edges ?? []).map((edge) => [
      edge.id,
      (edge as typeof edge & { sections?: Parameters<typeof orthogonalPath>[0] }).sections,
    ]),
  );
  const nodes = visible.nodes.map<FlowNode>((node) => {
    const positioned = positions.get(node.data.id);
    const size = measured.get(node.data.id) ?? nodeDimensions(node.data);
    return {
      id: node.data.id,
      position: { x: positioned?.x ?? 0, y: positioned?.y ?? 0 },
      data: {
        ...node.data,
        in_ports: node.data.in_ports,
        out_ports: node.data.out_ports,
        onInputSourceAction,
      },
      type: "dag",
      style: size,
    };
  });
  const edges = visible.edges.map<Edge<FlowEdgeData>>((entry: GraphEdge) => {
    const edge = entry.data;
    const sourceNode = visible.nodes.find((node) => node.data.id === edge.source_node_id);
    const color = sourceNode?.data.colors.border ?? edge.style.color;
    const isMain = edge.kind === "main";
    // A wire represents its producer. Its visual treatment must therefore be
    // derived only from the source node, never from its consumer.
    const isVirtualSource = Boolean(sourceNode?.data.isLineageVirtual);
    return {
      id: edge.id,
      ...edgeHandleMapping(edge),
      data: {
        orthogonalPath: orthogonalPath(sections.get(edge.id)),
        points: orthogonalPoints(sections.get(edge.id)),
        dtype: edge.dtype,
        color,
      },
      className: `wfa-flow-edge wfa-flow-edge--${edge.kind} wfa-flow-edge--${edge.category}${isVirtualSource ? " wfa-flow-edge--virtual" : ""}`,
      style: {
        stroke: color,
        strokeWidth: isMain ? Math.max(edge.style.width, 3.15) : Math.max(edge.style.width, 2.25),
        opacity: isVirtualSource ? 0.72 : isMain ? 0.98 : 0.82,
        strokeDasharray: isVirtualSource ? "7 5" : undefined,
      },
    };
  });
  return { nodes, edges };
}

type Preview = { id: string; x: number; y: number; source: "click" | "hover" };

const KIND_LABELS: Record<string, string> = {
  raw_data: "原始数据",
  structured_array: "结构化数组",
  dataframe: "表格数据",
  grouped: "聚合/分组",
  side_effect: "导出/副作用",
  intermediate: "中间处理",
};

function kindLabel(kind: string) {
  return KIND_LABELS[kind] ?? kind;
}

function Lineage({ graph: staticGraph }: { graph: Graph }) {
  const params = new URLSearchParams(location.search);
  const debugLineage = params.get("debug") === "lineage";
  const initialView = params.get("view") ?? "overview";
  const [view, setView] = useState(initialView);
  const [selected, setSelected] = useState(params.get("focus") ?? "");
  const [graph, setGraph] = useState(staticGraph);
  const [graphSource, setGraphSource] = useState<"static" | "live" | "fallback">("static");
  const [flow, setFlow] = useState<{ nodes: FlowNode[]; edges: Edge<FlowEdgeData>[] }>(() => ({ nodes: seedNodes(staticGraph, initialView, params.get("focus") ?? ""), edges: [] }));
  const [fittedLayoutRevision, setFittedLayoutRevision] = useState(0);
  const [instance, setInstance] = useState<ReactFlowInstance<FlowNode, Edge<FlowEdgeData>> | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const previewRef = useRef(preview);
  const previewDismissTimer = useRef<number | null>(null);
  useEffect(() => { previewRef.current = preview; }, [preview]);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const [navigationHidden, setNavigationHidden] = useState(false);
  const [showVirtualNodes, setShowVirtualNodes] = useState(true);
  const [canToggleNavigation] = useState(
    () => Boolean(document.querySelector(".site-layout--lineage")),
  );
  const normalizedView = normalizeView(view);
  const canvasRef = useRef<HTMLDivElement>(null);
  const layoutRevisionRef = useRef(0);
  const displayGraph = useMemo(
    () => showVirtualNodes ? graph : withoutVirtualNodes(graph),
    [graph, showVirtualNodes],
  );
  const visibleSelected = displayGraph.nodes.some((node) => node.data.id === selected)
    ? selected
    : "";
  const layoutFocus = view === "focus" ? visibleSelected : "";
  const select = useCallback((id: string) => {
    setSelected(id);
    const url = new URL(location.href);
    url.searchParams.set("focus", id);
    history.replaceState({}, "", url);
  }, []);
  const centerNode = useCallback((id: string) => {
    const node = instance?.getNodes().find((entry) => entry.id === id);
    if (!instance || !node) return;
    // React Flow uses the measured node bounds here, so source-port navigation
    // remains centered even after ELK changes the surrounding layout.
    instance.fitView({
      nodes: [node],
      padding: 0.58,
      minZoom: 1.18,
      maxZoom: 1.18,
      duration: 240,
    });
  }, [instance]);
  const showPreview = useCallback((event: React.MouseEvent, id: string, source: "click" | "hover" = "click") => {
    const bounds = canvasRef.current?.getBoundingClientRect();
    const width = bounds?.width ?? 360;
    const height = bounds?.height ?? 540;
    const x = Math.min(Math.max(12, event.clientX - (bounds?.left ?? 0) + 14), Math.max(12, width - 292));
    const y = Math.min(Math.max(12, event.clientY - (bounds?.top ?? 0) + 14), Math.max(12, height - 276));
    setPreview({ id, x, y, source });
  }, []);
  const handleInputSourceAction = useCallback<InputSourceAction>((event, sourceId, action) => {
    if (action === "preview") {
      showPreview(event, sourceId, "click");
      return;
    }
    select(sourceId);
    centerNode(sourceId);
  }, [centerNode, select, showPreview]);

  const cancelDismiss = useCallback(() => {
    if (previewDismissTimer.current !== null) window.clearTimeout(previewDismissTimer.current);
    previewDismissTimer.current = null;
  }, []);
  const dismissPreview = useCallback((delay = 220) => {
    // A port-click preview stays pinned until explicitly closed, so hovering
    // away or leaving the panel must not auto-dismiss it.
    if (previewRef.current?.source === "click") return;
    if (previewDismissTimer.current !== null) window.clearTimeout(previewDismissTimer.current);
    previewDismissTimer.current = window.setTimeout(() => {
      previewDismissTimer.current = null;
      setPreview(null);
    }, delay);
  }, []);
  const closePreview = useCallback(() => {
    cancelDismiss();
    setPreview(null);
  }, [cancelDismiss]);
  const handleNodeMouseEnter = useCallback((event: React.MouseEvent, node: FlowNode) => {
    cancelDismiss();
    if (previewRef.current?.source === "click") return;
    showPreview(event, node.id, "hover");
  }, [cancelDismiss, showPreview]);
  const handleNodeMouseLeave = useCallback(() => {
    if (previewRef.current?.source === "click") return;
    dismissPreview();
  }, [dismissPreview]);
  useEffect(() => () => {
    if (previewDismissTimer.current !== null) window.clearTimeout(previewDismissTimer.current);
  }, []);

  useEffect(() => {
    if (params.get("lineage") !== "live") return;
    let cancelled = false;
    fetch(new URL("/api/lineage", location.href), { headers: { Accept: "application/json" } })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<Graph>;
      })
      .then((liveGraph) => {
        if (cancelled || !Array.isArray(liveGraph.nodes) || !Array.isArray(liveGraph.edges)) return;
        setGraph(liveGraph);
        setGraphSource("live");
      })
      .catch(() => {
        if (!cancelled) setGraphSource("fallback");
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!instance) return;
    const layoutRevision = ++layoutRevisionRef.current;
    let cancelled = false;
    const frame = requestAnimationFrame(() => {
      const measured = new Map(instance.getNodes().map((node) => [node.id, {
        width: node.measured?.width ?? (Number(node.width) || nodeDimensions(node.data).width),
        height: node.measured?.height ?? (Number(node.height) || nodeDimensions(node.data).height),
      }]));
      layout(displayGraph, view, layoutFocus, measured, handleInputSourceAction).then((next) => {
        if (cancelled || layoutRevision !== layoutRevisionRef.current) return;
        setFlow(next);
        setFittedLayoutRevision(layoutRevision);
        if (debugLineage) {
          const visible = visibleGraph(displayGraph, view, layoutFocus);
          const visibleNodeIds = new Set(visible.nodes.map((node) => node.data.id));
          const invalid = invalidConnections(displayGraph).filter((edge) =>
            visibleNodeIds.has(edge.data.source_node_id)
              || visibleNodeIds.has(edge.data.target_node_id),
          );
          const fallbackEdges = next.edges.filter(
            (edge) => !edge.data?.orthogonalPath,
          ).length;
          console.info("[lineage] layout", {
            view: view === "focus" ? "focus" : normalizeView(view),
            nodes: visible.nodes.length,
            ports: visible.nodes.reduce(
              (count, node) =>
                count + node.data.in_ports.length + node.data.out_ports.length,
              0,
            ),
            edges: visible.edges.length,
            invalidConnections: invalid.length,
            orthogonalEdges: next.edges.length - fallbackEdges,
            fallbackEdges,
          });
        }
      });
    });
    return () => { cancelled = true; cancelAnimationFrame(frame); };
  }, [debugLineage, displayGraph, handleInputSourceAction, instance, layoutFocus, view]);

  useEffect(() => {
    if (!instance || !flow.nodes.length || !fittedLayoutRevision) return;
    const frame = requestAnimationFrame(() => {
      instance.fitView({ padding: 0.16, maxZoom: 1.05, duration: 0 });
    });
    return () => cancelAnimationFrame(frame);
  }, [fittedLayoutRevision, flow.nodes, instance]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!instance || !canvas || !flow.nodes.length || !fittedLayoutRevision) return;
    let frame = 0;
    const refit = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        instance.fitView({ padding: 0.16, maxZoom: 1.05, duration: 0 });
      });
    };
    const observer = new ResizeObserver(refit);
    observer.observe(canvas);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [fittedLayoutRevision, flow.nodes.length, instance]);

  useEffect(() => {
    if (!debugLineage) return;
    const invalid = invalidConnections(displayGraph);
    console.info("[lineage] graph", {
      nodes: displayGraph.nodes.length,
      ports: displayGraph.nodes.reduce((count, node) => count + node.data.in_ports.length + node.data.out_ports.length, 0),
      edges: displayGraph.edges.length,
      invalidConnections: invalid.length,
    });
    if (invalid.length) console.table(invalid.map((edge) => edge.data));
  }, [debugLineage, displayGraph]);

  useEffect(() => {
    const layoutElement = document.querySelector<HTMLElement>(".site-layout--lineage");
    if (!layoutElement) return;
    layoutElement.classList.toggle("is-navigation-hidden", navigationHidden);
    return () => layoutElement.classList.remove("is-navigation-hidden");
  }, [navigationHidden]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closePreview();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [closePreview]);

  const changeView = useCallback((next: string) => {
    setView(next);
    const url = new URL(location.href);
    url.searchParams.set("view", next);
    history.replaceState({}, "", url);
  }, []);

  const previewNode = useMemo(
    () => displayGraph.nodes.find((node) => node.data.id === preview?.id)?.data,
    [displayGraph, preview],
  );
  const previewRelation = previewNode ? displayGraph.relations[previewNode.id] : undefined;

  return <section className="wfa-flow-shell" aria-label="插件依赖 DAG">
    <div className="wfa-flow-toolbar" role="group" aria-label="谱系视图">
      {[["overview", "Overview"], ["full", "Full DAG"]].map(([value, label]) => <button key={value} type="button" className={normalizedView === value ? "is-active" : ""} onClick={() => changeView(value)}>{label}</button>)}
      <label className="wfa-flow-virtual-toggle" title="显示或隐藏虚拟计算节点">
        <input type="checkbox" checked={showVirtualNodes} onChange={(event) => { setShowVirtualNodes(event.target.checked); closePreview(); }} />
        <span className="wfa-flow-virtual-toggle-track" aria-hidden="true" />
        <span>虚拟节点</span>
      </label>
      {canToggleNavigation && <button className="wfa-flow-nav-toggle" type="button" aria-label={navigationHidden ? "显示左侧导航" : "隐藏左侧导航"} title={navigationHidden ? "显示左侧导航" : "隐藏左侧导航"} onClick={() => setNavigationHidden((value) => !value)}><span className="wfa-flow-nav-toggle-icon" aria-hidden="true" /></button>}
      {graphSource !== "static" && <span className="wfa-flow-source" role="status">{graphSource === "live" ? "Live Context" : "Static fallback"}</span>}
    </div>
    <div className="wfa-flow-canvas" ref={canvasRef}>
      <WireLayer edges={flow.edges} viewport={viewport} />
      <ReactFlow<FlowNode, Edge<FlowEdgeData>> nodes={flow.nodes} edges={[]} nodeTypes={nodeTypes} onInit={setInstance} onViewportChange={setViewport} minZoom={MIN_CANVAS_ZOOM} maxZoom={1.5} nodesDraggable={false} panOnScroll panOnScrollMode={PanOnScrollMode.Free} zoomOnScroll zoomActivationKeyCode={["Control", "Meta"]} onNodeClick={(_, node) => location.assign(String(node.data.href))} onNodeMouseEnter={handleNodeMouseEnter} onNodeMouseLeave={handleNodeMouseLeave} onPaneClick={closePreview}>
        <Background gap={18} />
        {normalizedView === "full" && <MiniMap zoomable pannable position="bottom-right" style={{ width: 132, height: 92 }} />}
        <Controls />
      </ReactFlow>
      {previewNode && preview && <aside className="wfa-flow-preview" style={{ left: preview.x, top: preview.y }} aria-label={`${previewNode.label} 预览`} onMouseEnter={cancelDismiss} onMouseLeave={() => dismissPreview()}>
        <button type="button" className="wfa-flow-preview-close" aria-label="关闭节点预览" onClick={closePreview}>×</button>
        <strong>{previewNode.id}</strong><span>{previewNode.pluginClass}</span>
        {previewNode.summary && <p>{previewNode.summary}</p>}
        <dl><dt>输入</dt><dd>{previewNode.in_ports.map((port) => port.name).join(", ") || "无"}</dd><dt>输出</dt><dd>{previewNode.out_ports.map((port) => port.name).join(", ") || "无"}</dd><dt>下游</dt><dd>{previewRelation?.consumers.join(", ") || "无"}</dd><dt>分类</dt><dd>{kindLabel(previewNode.kind)}</dd><dt>集合</dt><dd>{previewNode.pluginSet}</dd></dl>
        <a href={previewNode.href}>打开完整文档</a>
      </aside>}
    </div>
  </section>;
}

function mountLineage() {
  const target = document.querySelector<HTMLElement>("[data-react-lineage]");
  const source = document.querySelector<HTMLScriptElement>("#lineage-graph-data");
  if (!target || !source) return;
  createRoot(target).render(<Lineage graph={JSON.parse(source.textContent ?? "{}") as Graph} />);
}

mountLineage();
