import {
  SEARCH_INDEX_SCHEMA,
  searchIndexFingerprint,
  type SearchEntry,
  type SearchIndex,
  type SearchIndexPayload,
} from "./search";

export type { SearchEntry, SearchIndex, SearchIndexPayload } from "./search";

export class SearchIndexValidationError extends Error {
  constructor(message: string) {
    super(`Invalid search-index/v1: ${message}`);
    this.name = "SearchIndexValidationError";
  }
}

export type SearchIndexValidationOptions = {
  expectedFingerprint?: string;
  expectedModelVersion?: string;
};

export type SearchIndexFetcher = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, path: string, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    throw new SearchIndexValidationError(`${path} must be a string${allowEmpty ? "" : " and non-empty"}`);
  }
  return value;
}

function validateEntry(value: unknown, index: number): SearchEntry {
  if (!isRecord(value)) {
    throw new SearchIndexValidationError(`entries[${index}] must be an object`);
  }
  const path = `entries[${index}]`;
  const anchor = value.anchor;
  if (anchor !== undefined && anchor !== null && typeof anchor !== "string") {
    throw new SearchIndexValidationError(`${path}.anchor must be a string when present`);
  }
  return {
    title: requiredString(value.title, `${path}.title`),
    summary: requiredString(value.summary, `${path}.summary`),
    kind: requiredString(value.kind, `${path}.kind`),
    url: requiredString(value.url, `${path}.url`),
    keywords: requiredString(value.keywords, `${path}.keywords`, true),
    ...(typeof anchor === "string" ? { anchor } : {}),
  };
}

export function validateSearchIndex(
  value: unknown,
  options: SearchIndexValidationOptions = {},
): SearchIndex {
  if (!isRecord(value)) throw new SearchIndexValidationError("root must be an object");
  const schema = requiredString(value.schema, "root.schema");
  if (schema !== SEARCH_INDEX_SCHEMA) {
    throw new SearchIndexValidationError(`schema must equal ${SEARCH_INDEX_SCHEMA}`);
  }
  const modelVersion = requiredString(value.modelVersion, "root.modelVersion");
  if (options.expectedModelVersion !== undefined && modelVersion !== options.expectedModelVersion) {
    throw new SearchIndexValidationError(
      `modelVersion mismatch: expected ${options.expectedModelVersion}, got ${modelVersion}`,
    );
  }
  const fingerprint = requiredString(value.fingerprint, "root.fingerprint");
  if (!/^[a-f0-9]{64}$/.test(fingerprint)) {
    throw new SearchIndexValidationError("root.fingerprint must be a lowercase SHA-256 digest");
  }
  if (!Array.isArray(value.entries) || value.entries.length === 0) {
    throw new SearchIndexValidationError("root.entries must be a non-empty array");
  }
  const entries = value.entries.map(validateEntry);
  const payload: SearchIndexPayload = {
    schema: SEARCH_INDEX_SCHEMA,
    modelVersion,
    entries,
  };
  const computedFingerprint = searchIndexFingerprint(payload);
  if (computedFingerprint !== fingerprint) {
    throw new SearchIndexValidationError(
      `fingerprint mismatch: payload computes ${computedFingerprint}, document declares ${fingerprint}`,
    );
  }
  if (options.expectedFingerprint !== undefined && fingerprint !== options.expectedFingerprint) {
    throw new SearchIndexValidationError(
      `fingerprint mismatch: expected ${options.expectedFingerprint}, got ${fingerprint}`,
    );
  }
  return { ...payload, fingerprint };
}

const searchIndexPromises = new Map<string, Promise<SearchIndex>>();

function defaultFetcher(input: string, init?: RequestInit): Promise<Response> {
  if (typeof fetch !== "function") {
    return Promise.reject(new SearchIndexValidationError("fetch is not available"));
  }
  return fetch(input, init);
}

export type LoadSearchIndexOptions = SearchIndexValidationOptions & {
  fetcher?: SearchIndexFetcher;
};

export function loadSearchIndex(
  href: string,
  expectedFingerprint: string,
  fetcher?: SearchIndexFetcher,
  expectedModelVersion?: string,
): Promise<SearchIndex>;
export function loadSearchIndex(
  href: string,
  options: LoadSearchIndexOptions,
): Promise<SearchIndex>;
export function loadSearchIndex(
  href: string,
  expectedOrOptions: string | LoadSearchIndexOptions,
  fetcher?: SearchIndexFetcher,
  expectedModelVersion?: string,
): Promise<SearchIndex> {
  if (!href) return Promise.reject(new SearchIndexValidationError("index href is required"));
  const options: LoadSearchIndexOptions = typeof expectedOrOptions === "string"
    ? { expectedFingerprint: expectedOrOptions, expectedModelVersion, fetcher }
    : expectedOrOptions;
  const cached = searchIndexPromises.get(href);
  if (cached) return cached;

  const request = Promise.resolve()
    .then(() => (options.fetcher ?? defaultFetcher)(href, {
      headers: { accept: "application/json" },
      // The URL is stable across model releases; the shell fingerprint must
      // be able to detect a stale HTTP cache and retry a fresh copy.
      cache: "no-cache",
    }))
    .then((response) => {
      if (!response.ok) {
        throw new SearchIndexValidationError(`request failed with HTTP ${response.status}`);
      }
      return response.json();
    })
    .then((payload) => validateSearchIndex(payload, options));

  let pending: Promise<SearchIndex>;
  pending = request.catch((error: unknown) => {
    if (searchIndexPromises.get(href) === pending) searchIndexPromises.delete(href);
    throw error;
  });
  searchIndexPromises.set(href, pending);
  return pending;
}

/** Clear a failed/superseded URL, or all cached URLs in tests and retry UI. */
export function clearSearchIndexCache(href?: string): void {
  if (href === undefined) searchIndexPromises.clear();
  else searchIndexPromises.delete(href);
}

export const resetSearchIndexCache = clearSearchIndexCache;
