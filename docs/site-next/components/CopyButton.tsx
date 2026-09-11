"use client";

import { useState } from "react";
import { Icon } from "./icons";

export function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return <button className="copy-button" type="button" onClick={copy} aria-label={copied ? "已复制代码" : "复制代码"} title={copied ? "已复制" : "复制代码"}>
    <Icon name={copied ? "checkmark" : "copy"} size={17} /> <span>{copied ? "已复制" : "复制"}</span>
  </button>;
}
