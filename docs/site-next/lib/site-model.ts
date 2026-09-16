export const SITE_MODEL_SCHEMA = "site-model/v1" as const;

export type SiteModelSchema = typeof SITE_MODEL_SCHEMA;

export type NavigationItem = {
  label: string;
  href: string;
  icon: string;
  children?: NavigationItem[];
};

export type NavigationGroup = {
  id: string;
  title: string;
  items: NavigationItem[];
};

export type ConfigEntry = {
  name: string;
  value: string;
  description: string;
};

export type OutputField = {
  name: string;
  dtype: string;
  unit: string;
  description: string;
};

export type InlineContent = {
  kind: "text" | "code" | "link" | "image";
  text: string;
  href?: string;
};

export type GuideListNode = {
  ordered: boolean;
  start?: number;
  entries: { text: string; inlines?: InlineContent[]; children?: GuideListNode[] }[];
};

export type ReferenceContentBlock = {
  kind: "paragraph" | "heading" | "list" | "note" | "code" | "image" | "mathml" | "mermaid" | "table";
  text?: string;
  inlines?: InlineContent[];
  items?: string[];
  item_inlines?: InlineContent[][];
  list_tree?: GuideListNode;
  ordered?: boolean;
  heading_level?: 2 | 3 | 4 | 5 | 6;
  title?: string;
  tone?: string;
  code?: string;
  language?: string;
  image_src?: string;
  image_alt?: string;
  image_caption?: string;
  mathml?: string;
  mermaid?: string;
  table_headers?: string[];
  table_rows?: string[][];
  table_inlines?: InlineContent[][][];
};

export type ReferenceSection = {
  id: string;
  title: string;
  blocks: ReferenceContentBlock[];
};

export type PluginModel = {
  provides: string;
  pluginClass?: string;
  version: string | null;
  executionKind: "static" | "streaming" | "unknown";
  outputKind: string;
  category: string;
  summary: string;
  dependsOn: string[];
  config: ConfigEntry[];
  fields: OutputField[];
  usage: string;
  sections: ReferenceSection[];
  route: string;
  provenance: "generated" | "fixture";
};

export type ContextModel = {
  slug: string;
  name: string;
  summary: string;
  profiles: string[];
  examples: string[];
  sections: ReferenceSection[];
  route: string;
  provenance: "generated" | "fixture";
};

export type AccessorModel = {
  slug: string;
  name: string;
  summary: string;
  inputs: string[];
  methods: string[];
  pageKind: "class" | "callable";
  selection: {
    entry: string;
    question: string;
    scenario: string;
  };
  sections: ReferenceSection[];
  route: string;
  provenance: "generated" | "fixture";
};

export type VisualizationModel = {
  slug: string;
  name: string;
  summary: string;
  outputs: string[];
  sections: ReferenceSection[];
  route: string;
  provenance: "generated" | "fixture";
};

export type GuideSection = {
  id: string;
  title: string;
  blocks: ReferenceContentBlock[];
  // Deprecated compatibility projection for the pre-S1 search consumer.
  paragraphs: string[];
  bullets?: string[];
  table?: {
    headers: string[];
    rows: string[][];
  };
  code?: string;
};

export type GuideModel = {
  slug: string;
  title: string;
  section: string;
  summary: string;
  sections: GuideSection[];
  source?: string;
  source_sha256?: string;
  model_fingerprint?: string;
  block_types?: string[];
  content_counts?: Record<string, number>;
  source_indexes?: SourceIndexSummary[];
  route: string;
  provenance: "generated" | "fixture";
};

export type SourceIndexSummary = {
  section_id: string;
  route: string;
  source: string;
  title: string;
  summary: string;
  source_sha256: string;
  model_fingerprint: string;
  block_types: string[];
  content_counts: Record<string, number>;
};

export type SourceIndexModel = SourceIndexSummary & {
  sections: GuideSection[];
  provenance: "generated" | "fixture";
};

export type LineagePort = {
  id: string;
  name: string;
  dtype: string;
  side: "input" | "output";
};

export type LineageNode = {
  id: string;
  label: string;
  pluginClass: string;
  kind: "raw" | "record" | "signal" | "peak" | "event" | "virtual";
  summary: string;
  version: string | null;
  inputs: LineagePort[];
  outputs: LineagePort[];
};

export type LineageEdge = {
  id: string;
  source: string;
  sourcePort: string;
  target: string;
  targetPort: string;
  dtype: string;
  kind: "main" | "branch" | "virtual";
};

export type LineageModel = {
  nodes: LineageNode[];
  edges: LineageEdge[];
  views: {
    overview: string[];
    full: string[];
  };
};

export type RouteEntry = {
  path: string;
  title: string;
  kind: "home" | "plugin" | "context" | "accessor" | "visualization" | "lineage" | "guide";
};

export type SiteModel = {
  schema: SiteModelSchema;
  modelVersion: string;
  project: {
    name: string;
    version: string;
    tagline: string;
  };
  provenance: "generated" | "fixture";
  navigation: NavigationGroup[];
  routes: RouteEntry[];
  plugins: PluginModel[];
  contexts: ContextModel[];
  accessors: AccessorModel[];
  visualizations: VisualizationModel[];
  guides: GuideModel[];
  source_indexes: SourceIndexModel[];
  lineage: LineageModel;
};

export class SiteModelValidationError extends Error {
  constructor(message: string) {
    super(`Invalid site-model/v1: ${message}`);
    this.name = "SiteModelValidationError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(record: Record<string, unknown>, key: string, path: string): string {
  const value = record[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new SiteModelValidationError(`${path}.${key} must be a non-empty string`);
  }
  return value;
}

function requiredStringArray(record: Record<string, unknown>, key: string, path: string): string[] {
  const value = record[key];
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    throw new SiteModelValidationError(`${path}.${key} must be a string[]`);
  }
  return value;
}

function optionalString(record: Record<string, unknown>, key: string, path: string): string | null {
  const value = record[key];
  if (value === null || value === undefined) return null;
  if (typeof value !== "string") {
    throw new SiteModelValidationError(`${path}.${key} must be string | null`);
  }
  return value;
}

function validatePorts(value: unknown, path: string, side: LineagePort["side"]): LineagePort[] {
  if (!Array.isArray(value)) throw new SiteModelValidationError(`${path} must be an array`);
  return value.map((item, index) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`${path}[${index}] must be an object`);
    const portPath = `${path}[${index}]`;
    return {
      id: requiredString(item, "id", portPath),
      name: requiredString(item, "name", portPath),
      dtype: requiredString(item, "dtype", portPath),
      side,
    };
  });
}

function validateLineage(value: unknown): LineageModel {
  if (!isRecord(value)) throw new SiteModelValidationError("lineage must be an object");
  const nodesValue = value.nodes;
  if (!Array.isArray(nodesValue)) throw new SiteModelValidationError("lineage.nodes must be an array");
  const nodes = nodesValue.map((item, index): LineageNode => {
    if (!isRecord(item)) throw new SiteModelValidationError(`lineage.nodes[${index}] must be an object`);
    const path = `lineage.nodes[${index}]`;
    const kind = requiredString(item, "kind", path);
    if (!["raw", "record", "signal", "peak", "event", "virtual"].includes(kind)) {
      throw new SiteModelValidationError(`${path}.kind is not supported`);
    }
    return {
      id: requiredString(item, "id", path),
      label: requiredString(item, "label", path),
      pluginClass: requiredString(item, "pluginClass", path),
      kind: kind as LineageNode["kind"],
      summary: requiredString(item, "summary", path),
      version: optionalString(item, "version", path),
      inputs: validatePorts(item.inputs, `${path}.inputs`, "input"),
      outputs: validatePorts(item.outputs, `${path}.outputs`, "output"),
    };
  });
  const nodeIds = new Set(nodes.map((node) => node.id));
  if (nodeIds.size !== nodes.length) throw new SiteModelValidationError("lineage node ids must be unique");
  if (!Array.isArray(value.edges)) throw new SiteModelValidationError("lineage.edges must be an array");
  const ports = new Map<string, LineagePort>();
  nodes.forEach((node) => [...node.inputs, ...node.outputs].forEach((port) => ports.set(`${node.id}:${port.id}`, port)));
  const edges = value.edges.map((item, index): LineageEdge => {
    if (!isRecord(item)) throw new SiteModelValidationError(`lineage.edges[${index}] must be an object`);
    const path = `lineage.edges[${index}]`;
    const edge = {
      id: requiredString(item, "id", path),
      source: requiredString(item, "source", path),
      sourcePort: requiredString(item, "sourcePort", path),
      target: requiredString(item, "target", path),
      targetPort: requiredString(item, "targetPort", path),
      dtype: requiredString(item, "dtype", path),
      kind: requiredString(item, "kind", path) as LineageEdge["kind"],
    };
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
      throw new SiteModelValidationError(`${path} references an unknown node`);
    }
    const sourcePort = ports.get(`${edge.source}:${edge.sourcePort}`);
    const targetPort = ports.get(`${edge.target}:${edge.targetPort}`);
    if (sourcePort?.side !== "output" || targetPort?.side !== "input") {
      throw new SiteModelValidationError(`${path} must connect output to input`);
    }
    return edge;
  });
  const viewsValue = value.views;
  if (!isRecord(viewsValue)) throw new SiteModelValidationError("lineage.views must be an object");
  const overview = requiredStringArray(viewsValue, "overview", "lineage.views");
  const full = requiredStringArray(viewsValue, "full", "lineage.views");
  [...overview, ...full].forEach((id) => {
    if (!nodeIds.has(id)) throw new SiteModelValidationError(`lineage view references unknown node ${id}`);
  });
  return { nodes, edges, views: { overview, full } };
}

function validateNavigationItem(value: unknown, path: string): NavigationItem {
  if (!isRecord(value)) throw new SiteModelValidationError(`${path} must be an object`);
  const childrenValue = value.children;
  if (childrenValue !== undefined && !Array.isArray(childrenValue)) {
    throw new SiteModelValidationError(`${path}.children must be an array`);
  }
  const item: NavigationItem = {
    label: requiredString(value, "label", path),
    href: requiredString(value, "href", path),
    icon: requiredString(value, "icon", path),
  };
  if (Array.isArray(childrenValue)) {
    item.children = childrenValue.map((child, index) =>
      validateNavigationItem(child, `${path}.children[${index}]`));
  }
  return item;
}

function validateNavigation(value: unknown): NavigationGroup[] {
  if (!Array.isArray(value)) throw new SiteModelValidationError("navigation must be an array");
  return value.map((item, index) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`navigation[${index}] must be an object`);
    const path = `navigation[${index}]`;
    const itemsValue = item.items;
    if (!Array.isArray(itemsValue)) throw new SiteModelValidationError(`${path}.items must be an array`);
    return {
      id: requiredString(item, "id", path),
      title: requiredString(item, "title", path),
      items: itemsValue.map((entry, entryIndex) =>
        validateNavigationItem(entry, `${path}.items[${entryIndex}]`)),
    };
  });
}

function validateRoutes(value: unknown): RouteEntry[] {
  if (!Array.isArray(value)) throw new SiteModelValidationError("routes must be an array");
  const routes = value.map((item, index) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`routes[${index}] must be an object`);
    const path = `routes[${index}]`;
    const kind = requiredString(item, "kind", path);
    if (!["home", "plugin", "context", "accessor", "visualization", "lineage", "guide"].includes(kind)) {
      throw new SiteModelValidationError(`${path}.kind is not supported`);
    }
    return {
      path: requiredString(item, "path", path),
      title: requiredString(item, "title", path),
      kind: kind as RouteEntry["kind"],
    };
  });
  const paths = new Set(routes.map((route) => route.path));
  if (paths.size !== routes.length) throw new SiteModelValidationError("routes must not contain duplicate paths");
  if (routes.some((route) => route.path.endsWith(".html"))) {
    throw new SiteModelValidationError("routes must use extensionless paths");
  }
  return routes;
}

function validateCollection<T>(value: unknown, name: string, validate: (value: unknown, index: number) => T): T[] {
  if (!Array.isArray(value)) throw new SiteModelValidationError(`${name} must be an array`);
  return value.map(validate);
}

function optionalBoolean(record: Record<string, unknown>, key: string, path: string): boolean | undefined {
  const value = record[key];
  if (value === undefined) return undefined;
  if (typeof value !== "boolean") throw new SiteModelValidationError(`${path}.${key} must be boolean`);
  return value;
}

function optionalStringArrayValue(record: Record<string, unknown>, key: string, path: string): string[] | undefined {
  return record[key] === undefined ? undefined : requiredStringArray(record, key, path);
}

function validateStringRows(value: unknown, path: string): string[][] {
  if (!Array.isArray(value) || !value.every((row) => Array.isArray(row) && row.every((cell) => typeof cell === "string"))) {
    throw new SiteModelValidationError(`${path} must be string[][]`);
  }
  return value as string[][];
}

function validateInlineContent(value: unknown, path: string): InlineContent[] {
  if (!Array.isArray(value)) throw new SiteModelValidationError(`${path} must be an array`);
  return value.map((item, index) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`${path}[${index}] must be an object`);
    const itemPath = `${path}[${index}]`;
    const kind = requiredString(item, "kind", itemPath);
    if (!["text", "code", "link", "image"].includes(kind)) {
      throw new SiteModelValidationError(`${itemPath}.kind is not supported`);
    }
    const inline: InlineContent = {
      kind: kind as InlineContent["kind"],
      text: requiredString(item, "text", itemPath),
    };
    if (item.href !== undefined) inline.href = requiredString(item, "href", itemPath);
    if ((kind === "link" || kind === "image") && !inline.href) {
      throw new SiteModelValidationError(`${itemPath}.href is required for ${kind}`);
    }
    return inline;
  });
}

function validateInlineRows(value: unknown, path: string): InlineContent[][] {
  if (!Array.isArray(value)) throw new SiteModelValidationError(`${path} must be an array`);
  return value.map((row, index) => validateInlineContent(row, `${path}[${index}]`));
}

function validateInlineTable(value: unknown, path: string): InlineContent[][][] {
  if (!Array.isArray(value)) throw new SiteModelValidationError(`${path} must be an array`);
  return value.map((row, index) => validateInlineRows(row, `${path}[${index}]`));
}

function validateContentCounts(value: unknown, path: string): Record<string, number> {
  if (!isRecord(value)) throw new SiteModelValidationError(`${path} must be an object`);
  const result: Record<string, number> = {};
  for (const [key, count] of Object.entries(value)) {
    if (typeof count !== "number" || !Number.isInteger(count) || count < 0) {
      throw new SiteModelValidationError(`${path}.${key} must be a non-negative integer`);
    }
    result[key] = count;
  }
  return result;
}

function optionalSha256(record: Record<string, unknown>, key: string, path: string): string | undefined {
  const value = record[key];
  if (value === undefined) return undefined;
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) {
    throw new SiteModelValidationError(`${path}.${key} must be a SHA-256 hex digest`);
  }
  return value;
}

function validateGuideList(value: unknown, path: string): GuideListNode {
  if (!isRecord(value)) throw new SiteModelValidationError(`${path} must be an object`);
  if (typeof value.ordered !== "boolean") throw new SiteModelValidationError(`${path}.ordered must be a boolean`);
  const start = value.start;
  if (start !== undefined && (typeof start !== "number" || !Number.isSafeInteger(start) || start < 0)) {
    throw new SiteModelValidationError(`${path}.start must be a non-negative safe integer`);
  }
  return {
    ordered: value.ordered,
    start: start as number | undefined,
    entries: validateCollection(value.entries, `${path}.entries`, (entry, index) => {
      const entryPath = `${path}.entries[${index}]`;
      if (!isRecord(entry)) throw new SiteModelValidationError(`${entryPath} must be an object`);
      return {
        text: requiredString(entry, "text", entryPath),
        inlines: entry.inlines === undefined ? undefined : validateInlineContent(entry.inlines, `${entryPath}.inlines`),
        children: entry.children === undefined ? undefined : validateCollection(entry.children, `${entryPath}.children`, (child, childIndex) => validateGuideList(child, `${entryPath}.children[${childIndex}]`)),
      };
    }),
  };
}

function validateReferenceSections(value: unknown, path: string): ReferenceSection[] {
  return validateCollection(value, path, (section, sectionIndex) => {
    if (!isRecord(section)) throw new SiteModelValidationError(`${path}[${sectionIndex}] must be an object`);
    const sectionPath = `${path}[${sectionIndex}]`;
    const blocks = validateCollection(section.blocks, `${sectionPath}.blocks`, (block, blockIndex): ReferenceContentBlock => {
      if (!isRecord(block)) throw new SiteModelValidationError(`${sectionPath}.blocks[${blockIndex}] must be an object`);
      const blockPath = `${sectionPath}.blocks[${blockIndex}]`;
      const kind = requiredString(block, "kind", blockPath);
      if (!["paragraph", "heading", "list", "note", "code", "image", "mathml", "mermaid", "table"].includes(kind)) {
        throw new SiteModelValidationError(`${blockPath}.kind is not supported`);
      }
      const headingLevel = block.heading_level;
      if (headingLevel !== undefined && ![2, 3, 4, 5, 6].includes(headingLevel as number)) {
        throw new SiteModelValidationError(`${blockPath}.heading_level must be between 2 and 6`);
      }
      return {
        kind: kind as ReferenceContentBlock["kind"],
        text: optionalString(block, "text", blockPath) ?? undefined,
        inlines: block.inlines === undefined ? undefined : validateInlineContent(block.inlines, `${blockPath}.inlines`),
        items: optionalStringArrayValue(block, "items", blockPath),
        item_inlines: block.item_inlines === undefined ? undefined : validateInlineRows(block.item_inlines, `${blockPath}.item_inlines`),
        ordered: optionalBoolean(block, "ordered", blockPath),
        list_tree: block.list_tree === undefined ? undefined : validateGuideList(block.list_tree, `${blockPath}.list_tree`),
        heading_level: headingLevel as 2 | 3 | 4 | 5 | 6 | undefined,
        title: optionalString(block, "title", blockPath) ?? undefined,
        tone: optionalString(block, "tone", blockPath) ?? undefined,
        code: optionalString(block, "code", blockPath) ?? undefined,
        language: optionalString(block, "language", blockPath) ?? undefined,
        image_src: optionalString(block, "image_src", blockPath) ?? undefined,
        image_alt: optionalString(block, "image_alt", blockPath) ?? undefined,
        image_caption: optionalString(block, "image_caption", blockPath) ?? undefined,
        mathml: optionalString(block, "mathml", blockPath) ?? undefined,
        mermaid: optionalString(block, "mermaid", blockPath) ?? undefined,
        table_headers: optionalStringArrayValue(block, "table_headers", blockPath),
        table_rows: block.table_rows === undefined ? undefined : validateStringRows(block.table_rows, `${blockPath}.table_rows`),
        table_inlines: block.table_inlines === undefined ? undefined : validateInlineTable(block.table_inlines, `${blockPath}.table_inlines`),
      };
    });
    return { id: requiredString(section, "id", sectionPath), title: requiredString(section, "title", sectionPath), blocks };
  });
}

function validatePlugin(value: unknown, index: number): PluginModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`plugins[${index}] must be an object`);
  const path = `plugins[${index}]`;
  const executionKind = requiredString(value, "executionKind", path);
  if (!["static", "streaming", "unknown"].includes(executionKind)) {
    throw new SiteModelValidationError(`${path}.executionKind is not supported`);
  }
  const config = validateCollection(value.config, `${path}.config`, (item, itemIndex) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`${path}.config[${itemIndex}] must be an object`);
    const itemPath = `${path}.config[${itemIndex}]`;
    return {
      name: requiredString(item, "name", itemPath),
      value: requiredString(item, "value", itemPath),
      description: requiredString(item, "description", itemPath),
    };
  });
  const fields = validateCollection(value.fields, `${path}.fields`, (item, itemIndex) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`${path}.fields[${itemIndex}] must be an object`);
    const itemPath = `${path}.fields[${itemIndex}]`;
    return {
      name: requiredString(item, "name", itemPath),
      dtype: requiredString(item, "dtype", itemPath),
      unit: requiredString(item, "unit", itemPath),
      description: requiredString(item, "description", itemPath),
    };
  });
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  return {
    provides: requiredString(value, "provides", path),
    pluginClass: typeof value.pluginClass === "string" ? value.pluginClass : undefined,
    version: optionalString(value, "version", path),
    executionKind: executionKind as PluginModel["executionKind"],
    outputKind: requiredString(value, "outputKind", path),
    category: requiredString(value, "category", path),
    summary: requiredString(value, "summary", path),
    dependsOn: requiredStringArray(value, "dependsOn", path),
    config,
    fields,
    usage: requiredString(value, "usage", path),
    sections: validateReferenceSections(value.sections, `${path}.sections`),
    route: requiredString(value, "route", path),
    provenance: provenance as PluginModel["provenance"],
  };
}

function validateContext(value: unknown, index: number): ContextModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`contexts[${index}] must be an object`);
  const path = `contexts[${index}]`;
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  return {
    slug: requiredString(value, "slug", path), name: requiredString(value, "name", path), summary: requiredString(value, "summary", path),
    profiles: requiredStringArray(value, "profiles", path), examples: requiredStringArray(value, "examples", path),
    sections: validateReferenceSections(value.sections, `${path}.sections`), route: requiredString(value, "route", path),
    provenance: provenance as ContextModel["provenance"],
  };
}

function validateAccessor(value: unknown, index: number): AccessorModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`accessors[${index}] must be an object`);
  const path = `accessors[${index}]`;
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  const pageKind = requiredString(value, "pageKind", path);
  if (!["class", "callable"].includes(pageKind)) throw new SiteModelValidationError(`${path}.pageKind is not supported`);
  if (!isRecord(value.selection)) throw new SiteModelValidationError(`${path}.selection must be an object`);
  return {
    slug: requiredString(value, "slug", path), name: requiredString(value, "name", path), summary: requiredString(value, "summary", path),
    inputs: requiredStringArray(value, "inputs", path), methods: requiredStringArray(value, "methods", path),
    pageKind: pageKind as AccessorModel["pageKind"],
    selection: {
      entry: requiredString(value.selection, "entry", `${path}.selection`),
      question: requiredString(value.selection, "question", `${path}.selection`),
      scenario: requiredString(value.selection, "scenario", `${path}.selection`),
    },
    sections: validateReferenceSections(value.sections, `${path}.sections`), route: requiredString(value, "route", path),
    provenance: provenance as AccessorModel["provenance"],
  };
}

function validateVisualization(value: unknown, index: number): VisualizationModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`visualizations[${index}] must be an object`);
  const path = `visualizations[${index}]`;
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  return {
    slug: requiredString(value, "slug", path), name: requiredString(value, "name", path), summary: requiredString(value, "summary", path),
    outputs: requiredStringArray(value, "outputs", path), sections: validateReferenceSections(value.sections, `${path}.sections`), route: requiredString(value, "route", path),
    provenance: provenance as VisualizationModel["provenance"],
  };
}

function validateGuide(value: unknown, index: number): GuideModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`guides[${index}] must be an object`);
  const path = `guides[${index}]`;
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  const sections = validateCollection(value.sections, `${path}.sections`, (item, sectionIndex) => {
    if (!isRecord(item)) throw new SiteModelValidationError(`${path}.sections[${sectionIndex}] must be an object`);
    const sectionPath = `${path}.sections[${sectionIndex}]`;
    const blocks = validateReferenceSections([item], `${sectionPath}`).at(0)?.blocks ?? [];
    const section: GuideSection = {
      id: requiredString(item, "id", sectionPath), title: requiredString(item, "title", sectionPath),
      blocks,
      paragraphs: requiredStringArray(item, "paragraphs", sectionPath),
    };
    if (item.bullets !== undefined) section.bullets = requiredStringArray(item, "bullets", sectionPath);
    if (item.code !== undefined) section.code = requiredString(item, "code", sectionPath);
    if (item.table !== undefined) {
      if (!isRecord(item.table)) throw new SiteModelValidationError(`${sectionPath}.table must be an object`);
      section.table = {
        headers: requiredStringArray(item.table, "headers", `${sectionPath}.table`),
        rows: Array.isArray(item.table.rows) && item.table.rows.every((row) => Array.isArray(row) && row.every((cell) => typeof cell === "string"))
          ? item.table.rows as string[][]
          : (() => { throw new SiteModelValidationError(`${sectionPath}.table.rows must be string[][]`); })(),
      };
    }
    return section;
  });
  return {
    slug: requiredString(value, "slug", path), title: requiredString(value, "title", path), section: requiredString(value, "section", path),
    summary: requiredString(value, "summary", path), sections, route: requiredString(value, "route", path),
    source: typeof value.source === "string" ? value.source : undefined,
    source_sha256: optionalSha256(value, "source_sha256", path),
    model_fingerprint: optionalSha256(value, "model_fingerprint", path),
    block_types: value.block_types === undefined ? undefined : requiredStringArray(value, "block_types", path),
    content_counts: value.content_counts === undefined ? undefined : validateContentCounts(value.content_counts, `${path}.content_counts`),
    source_indexes: value.source_indexes === undefined ? undefined : validateCollection(value.source_indexes, `${path}.source_indexes`, validateSourceIndexSummary),
    provenance: provenance as GuideModel["provenance"],
  };
}

function validateSourceIndexSummary(value: unknown, index: number): SourceIndexSummary {
  if (!isRecord(value)) throw new SiteModelValidationError(`source index summary[${index}] must be an object`);
  const path = `source index summary[${index}]`;
  const sourceSha256 = optionalSha256(value, "source_sha256", path);
  const modelFingerprint = optionalSha256(value, "model_fingerprint", path);
  if (!sourceSha256 || !modelFingerprint) {
    throw new SiteModelValidationError(`${path}.source_sha256 and model_fingerprint are required`);
  }
  return {
    section_id: requiredString(value, "section_id", path),
    route: requiredString(value, "route", path),
    source: requiredString(value, "source", path),
    title: requiredString(value, "title", path),
    summary: requiredString(value, "summary", path),
    source_sha256: sourceSha256,
    model_fingerprint: modelFingerprint,
    block_types: requiredStringArray(value, "block_types", path),
    content_counts: validateContentCounts(value.content_counts, `${path}.content_counts`),
  };
}

function validateSourceIndex(value: unknown, index: number): SourceIndexModel {
  if (!isRecord(value)) throw new SiteModelValidationError(`source_indexes[${index}] must be an object`);
  const path = `source_indexes[${index}]`;
  const summary = validateSourceIndexSummary(value, index);
  const provenance = requiredString(value, "provenance", path);
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError(`${path}.provenance is not supported`);
  return {
    ...summary,
    sections: validateCollection(value.sections, `${path}.sections`, (item, sectionIndex) => {
      if (!isRecord(item)) throw new SiteModelValidationError(`${path}.sections[${sectionIndex}] must be an object`);
      const sectionPath = `${path}.sections[${sectionIndex}]`;
      const blocks = validateReferenceSections([item], sectionPath).at(0)?.blocks ?? [];
      return {
        id: requiredString(item, "id", sectionPath),
        title: requiredString(item, "title", sectionPath),
        blocks,
        paragraphs: requiredStringArray(item, "paragraphs", sectionPath),
        ...(item.bullets === undefined ? {} : { bullets: requiredStringArray(item, "bullets", sectionPath) }),
        ...(item.code === undefined ? {} : { code: requiredString(item, "code", sectionPath) }),
      };
    }),
    provenance: provenance as SourceIndexModel["provenance"],
  };
}

export function parseSiteModel(value: unknown): SiteModel {
  if (!isRecord(value)) throw new SiteModelValidationError("root must be an object");
  const schema = requiredString(value, "schema", "root");
  if (schema !== SITE_MODEL_SCHEMA) throw new SiteModelValidationError(`schema must equal ${SITE_MODEL_SCHEMA}`);
  if (!isRecord(value.project)) throw new SiteModelValidationError("project must be an object");
  const provenance = requiredString(value, "provenance", "root");
  if (!["generated", "fixture"].includes(provenance)) throw new SiteModelValidationError("root.provenance is not supported");
  const model: SiteModel = {
    schema: SITE_MODEL_SCHEMA,
    modelVersion: requiredString(value, "modelVersion", "root"),
    project: {
      name: requiredString(value.project, "name", "root.project"),
      version: requiredString(value.project, "version", "root.project"),
      tagline: requiredString(value.project, "tagline", "root.project"),
    },
    provenance: provenance as SiteModel["provenance"],
    navigation: validateNavigation(value.navigation),
    routes: validateRoutes(value.routes),
    plugins: validateCollection(value.plugins, "plugins", validatePlugin),
    contexts: validateCollection(value.contexts, "contexts", validateContext),
    accessors: validateCollection(value.accessors, "accessors", validateAccessor),
    visualizations: validateCollection(value.visualizations, "visualizations", validateVisualization),
    guides: validateCollection(value.guides, "guides", validateGuide),
    source_indexes: validateCollection(value.source_indexes, "source_indexes", validateSourceIndex),
    lineage: validateLineage(value.lineage),
  };
  const records = model.plugins.find((plugin) => plugin.provides === "records");
  if (!records || records.version !== "0.16.0" || records.dependsOn[0] !== "raw_files") {
    throw new SiteModelValidationError("records fixture must be v0.16.0 with raw_files as its first dependency");
  }
  if (!model.routes.some((route) => route.path === "/plugins/records/" && route.kind === "plugin")) {
    throw new SiteModelValidationError("records plugin route is missing");
  }
  return model;
}
