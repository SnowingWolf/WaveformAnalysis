"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { StaticLink as Link } from "./StaticLink";
import { Icon } from "./icons";
import {
  navigationSearchEntries,
  searchResults,
  type SearchEntry,
  type SiteShellModel,
} from "@/lib/search";
import {
  clearSearchIndexCache,
  loadSearchIndex,
  type SearchIndex,
} from "@/lib/search-index";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex=\"-1\"])",
].join(",");

function focusableElements(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (element) => !element.hidden && element.getAttribute("aria-hidden") !== "true",
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return "搜索索引暂时不可用";
}

export function SearchDialog({
  model,
  onClose,
}: {
  model: SiteShellModel;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const mountedRef = useRef(false);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState<SearchIndex | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const fallbackEntries = useMemo(() => navigationSearchEntries(model.navigation), [model.navigation]);
  const visibleEntries = status === "ready" && index
    ? index.entries
    : status === "error"
      ? fallbackEntries
      : [];
  const results = useMemo(
    () => searchResults(visibleEntries, query, 12),
    [query, visibleEntries],
  );
  const dialogId = `search-dialog-${useId().replace(/:/g, "")}`;
  const activeResult = results[selectedIndex];

  const requestIndex = useCallback(() => {
    setStatus("loading");
    setError(null);
    return loadSearchIndex(model.searchIndex.href, {
      expectedFingerprint: model.searchIndex.expectedFingerprint,
      expectedModelVersion: model.modelVersion,
    }).then((loaded) => {
      if (mountedRef.current) {
        setIndex(loaded);
        setStatus("ready");
      }
      return loaded;
    }).catch((reason: unknown) => {
      if (mountedRef.current) {
        setIndex(null);
        setStatus("error");
        setError(errorMessage(reason));
      }
      throw reason;
    });
  }, [model.modelVersion, model.searchIndex.expectedFingerprint, model.searchIndex.href]);

  useEffect(() => {
    mountedRef.current = true;
    void requestIndex().catch(() => undefined);
    return () => {
      mountedRef.current = false;
    };
  }, [requestIndex]);

  useEffect(() => {
    const previous = document.activeElement;
    inputRef.current?.focus();
    return () => {
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, []);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query, status]);

  const retry = () => {
    clearSearchIndexCache(model.searchIndex.href);
    void requestIndex().catch(() => undefined);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key === "ArrowDown" && results.length) {
      event.preventDefault();
      setSelectedIndex((current) => Math.min(current + 1, results.length - 1));
      return;
    }
    if (event.key === "ArrowUp" && results.length) {
      event.preventDefault();
      setSelectedIndex((current) => Math.max(current - 1, 0));
      return;
    }
    if (event.key === "Enter" && activeResult) {
      event.preventDefault();
      const result = document.getElementById(`${dialogId}-result-${selectedIndex}`);
      if (result instanceof HTMLAnchorElement) result.click();
      return;
    }
    if (event.key !== "Tab") return;
    const dialog = dialogRef.current;
    if (!dialog) return;
    const focusable = focusableElements(dialog);
    if (!focusable.length) {
      event.preventDefault();
      dialog.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div
      className="search-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        className="search-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${dialogId}-title`}
        aria-describedby={`${dialogId}-status`}
        tabIndex={-1}
        onKeyDown={onKeyDown}
      >
        <div className="search-dialog__head">
          <h2 id={`${dialogId}-title`}>搜索文档</h2>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭搜索">
            <Icon name="close" size={20} />
          </button>
        </div>
        <label className="search-input search-input--dialog">
          <Icon name="search" size={19} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索插件、Context 或指南"
            aria-label="搜索插件、Context 或指南"
            aria-controls={`${dialogId}-results`}
            aria-activedescendant={activeResult ? `${dialogId}-result-${selectedIndex}` : undefined}
          />
          <kbd>ESC</kbd>
        </label>
        <div id={`${dialogId}-status`} className="search-dialog__status" aria-live="polite">
          {status === "loading" && "正在加载搜索索引…"}
          {status === "error" && (
            <span className="search-dialog__error" role="alert">
              搜索索引暂时不可用，当前显示导航入口。
              <button type="button" className="search-retry" onClick={retry}>重试</button>
              {error && <span className="sr-only">{error}</span>}
            </span>
          )}
        </div>
        <div id={`${dialogId}-results`} className="search-results" role="listbox" aria-label="搜索结果">
          {results.length ? results.map((entry: SearchEntry, resultIndex) => (
            <Link
              key={`${entry.kind}:${entry.url}`}
              id={`${dialogId}-result-${resultIndex}`}
              href={entry.url}
              onClick={onClose}
              className={`search-result${resultIndex === selectedIndex ? " is-selected" : ""}`}
              role="option"
              aria-selected={resultIndex === selectedIndex}
              onMouseEnter={() => setSelectedIndex(resultIndex)}
            >
              <span className="search-result__kind">{entry.kind}</span>
              <span>
                <strong>{entry.title}</strong>
                <small>{entry.summary}</small>
              </span>
              <Icon name="arrow" size={16} />
            </Link>
          )) : status === "loading" ? null : (
            <p className="empty-state">没有匹配的文档。试试 `records` 或 `Context`。</p>
          )}
        </div>
        <footer className="search-dialog__footer">
          <span><kbd>↑↓</kbd> 选择结果</span>
          <span><kbd>↵</kbd> 打开结果</span>
          <span><kbd>ESC</kbd> 关闭</span>
        </footer>
      </section>
    </div>
  );
}
