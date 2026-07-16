import type { MetadataRoute } from "next";

const siteUrl = "https://eyeinthesky6.github.io/indexpilot";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      // Search visibility is separate from model-training access. Keep the
      // search and user-request agents explicit so future wildcard changes do
      // not accidentally remove IndexPilot from ChatGPT or Claude results.
      { userAgent: "OAI-SearchBot", allow: "/" },
      { userAgent: "Claude-SearchBot", allow: "/" },
      { userAgent: "Claude-User", allow: "/" },
      { userAgent: "*", allow: "/" },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
