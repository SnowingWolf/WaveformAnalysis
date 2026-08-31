import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "file" | "terminal" | "code" | "help" | "layers" | "database" | "nodes" | "cube" | "settings"
  | "puzzle" | "folder" | "api" | "search" | "architecture" | "check" | "contribute" | "release"
  | "sun" | "moon" | "github" | "arrow" | "chevron" | "menu" | "close" | "copy" | "checkmark" | "external"
  | "clock" | "fit" | "refresh" | "filter" | "book" | "panel";

type IconProps = SVGProps<SVGSVGElement> & { name: IconName; size?: number };

const paths: Record<IconName, ReactNode> = {
  file: <path d="M6 2.75h8.25L19 7.5v13.75H6zM14 2.75V8h5M9 12h7M9 16h7" />,
  terminal: <path d="m5 7 4 4-4 4M11.5 15H19M4 3h16v18H4z" />,
  code: <path d="m8 7-5 5 5 5M16 7l5 5-5 5M14 4l-4 16" />,
  help: <circle cx="12" cy="12" r="9" />,
  layers: <path d="m3 8 9-5 9 5-9 5-9-5Zm0 4 9 5 9-5M3 16l9 5 9-5M12 9v.01" />,
  database: <path d="M5 6c0-2 3.1-3.25 7-3.25S19 4 19 6v12c0 2-3.1 3.25-7 3.25S5 20 5 18V6Zm0 0c0 2 3.1 3.25 7 3.25S19 8 19 6M5 12c0 2 3.1 3.25 7 3.25S19 14 19 12" />,
  nodes: <path d="M5 5h4v4H5zM15 15h4v4h-4zM15 5h4v4h-4zM5 15h4v4H5zM9 7h6M7 9v6M17 9v6M9 17h6" />,
  cube: <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 0v9m8-4.5-8 4.5m-8-4.5 8 4.5" />,
  settings: <path d="M12 8.25a3.75 3.75 0 1 0 0 7.5 3.75 3.75 0 0 0 0-7.5Zm0-5.25v2.1m0 13.8v2.1M3.5 12h2.1m13.8 0h2.1M5.98 5.98l1.49 1.49m9.06 9.06 1.49 1.49m0-12.04-1.49 1.49m-9.06 9.06-1.49 1.49" />,
  puzzle: <path d="M9 3.5h3a2 2 0 1 1 4 0v1.25h2.25v4A2 2 0 1 1 18.25 13H17v4h-4a2 2 0 1 0-4 0H5v-4.25a2 2 0 1 1 0-4V5h4.25A2 2 0 1 1 9 3.5Z" />,
  folder: <path d="M3.5 6.5h6l1.75 2H20.5v10h-17z" />,
  api: <path d="M6 4.5h12v15H6zM9 8h6M9 12h6M9 16h3" />,
  search: <><circle cx="10.75" cy="10.75" r="6" /><path d="m15.25 15.25 5 5" /></>,
  architecture: <path d="M12 3v4m0 10v4M4 7h16M4 17h16M7 7v10m10-10v10" />,
  check: <path d="m4 12 5 5L20 6" />,
  contribute: <path d="M12 21a9 9 0 1 0-9-9c0 2.2.8 4.2 2.2 5.8L4 21l3.9-1.2A8.9 8.9 0 0 0 12 21Z" />,
  release: <path d="M5 19.5h14M7 16.5h10M9 13.5h6M12 3v7m0-7-3 3m3-3 3 3" />,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42m0-14.14-1.42 1.42m-11.3 11.3-1.42 1.42" /></>,
  moon: <path d="M20.5 15.3A8.5 8.5 0 0 1 8.7 3.5 8.5 8.5 0 1 0 20.5 15.3Z" />,
  github: <path d="M12 3a9 9 0 0 0-2.85 17.54c.45.08.62-.2.62-.43v-1.5c-2.52.55-3.05-1.07-3.05-1.07-.41-1.05-1-1.33-1-1.33-.82-.56.06-.55.06-.55.9.06 1.38.93 1.38.93.8 1.38 2.1.98 2.62.75.08-.58.31-.98.57-1.2-2.01-.23-4.13-1-4.13-4.47 0-.99.35-1.79.93-2.42-.09-.23-.4-1.15.09-2.4 0 0 .76-.24 2.48.92A8.6 8.6 0 0 1 12 8.47c.77 0 1.54.1 2.26.3 1.72-1.16 2.48-.92 2.48-.92.49 1.25.18 2.17.09 2.4.58.63.93 1.43.93 2.42 0 3.48-2.12 4.24-4.14 4.47.33.28.62.82.62 1.66v2.46c0 .24.16.52.62.43A9 9 0 0 0 12 3Z" />,
  arrow: <><path d="M3 12h16M14 6l6 6-6 6" /></>,
  chevron: <path d="m8 5 7 7-7 7" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  copy: <path d="M8 8V5h11v11h-3M5 8h11v11H5z" />,
  checkmark: <path d="m5 12 4 4L19 6" />,
  external: <path d="M14 5h5v5M19 5l-8 8M17 13v5H5V6h5" />,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
  fit: <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M21 16v5h-5" />,
  refresh: <path d="M20 11a8 8 0 0 0-14.6-3.6L4 9m0 0V5m0 4h4M4 13a8 8 0 0 0 14.6 3.6L20 15m0 0v4m0-4h-4" />,
  filter: <path d="M4 5h16l-6 7v5l-4 2v-7z" />,
  book: <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H19v16H6.5A2.5 2.5 0 0 0 4 21V5.5ZM4 5.5v15M8 7h7M8 11h7" />,
  panel: <path d="M4 4h16v16H4zM15 4v16" />,
};

export const iconNames = new Set<IconName>(Object.keys(paths) as IconName[]);

export function Icon({ name, size = 20, strokeWidth = 1.8, ...props }: IconProps) {
  return <svg aria-hidden="true" focusable="false" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" {...props}>{paths[name]}</svg>;
}
