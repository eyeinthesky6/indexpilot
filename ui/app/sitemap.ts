import type { MetadataRoute } from "next";
import { useCases } from "./use-cases/useCases";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: "https://eyeinthesky6.github.io/indexpilot/",
      changeFrequency: "weekly",
      priority: 1,
    },
    ...useCases.map(({ slug }) => ({ url: `https://eyeinthesky6.github.io/indexpilot/use-cases/${slug}/`, changeFrequency: "monthly" as const, priority: 0.8 })),
  ];
}
