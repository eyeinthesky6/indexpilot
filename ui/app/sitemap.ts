import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: "https://eyeinthesky6.github.io/indexpilot/",
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
