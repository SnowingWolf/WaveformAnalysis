import { loadSiteModel } from "@/lib/model";
import { buildSearchIndex } from "@/lib/search";

export const dynamic = "force-static";

export function GET(): Response {
  const index = buildSearchIndex(loadSiteModel());
  return new Response(JSON.stringify(index), {
    headers: {
      "cache-control": "public, max-age=0, must-revalidate",
      "content-type": "application/json; charset=utf-8",
    },
  });
}
