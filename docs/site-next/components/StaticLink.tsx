import type { AnchorHTMLAttributes } from "react";

/**
 * Documentation navigation deliberately uses normal HTTP links.
 *
 * The exported site is served as static files, and guide routes can overlap
 * with dynamic Next route families. A native anchor avoids RSC prefetch and
 * keeps navigation correct on every supported static HTTP server.
 */
export function StaticLink({ href, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  return <a href={href} {...props} />;
}
