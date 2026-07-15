import type { MetadataRoute } from "next";

const siteUrl = "https://eyeinthesky6.github.io/indexpilot";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
