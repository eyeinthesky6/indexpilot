import type { NextConfig } from "next";

const isGitHubPages = process.env.GITHUB_PAGES === "true";
const isBundledDashboard = process.env.INDEXPILOT_BUNDLED_UI === "true";
const repositoryBasePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "/indexpilot";

const nextConfig: NextConfig = isBundledDashboard
  ? {
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : isGitHubPages
  ? {
      output: "export",
      basePath: repositoryBasePath,
      assetPrefix: repositoryBasePath,
      trailingSlash: true,
      images: { unoptimized: true },
    }
  : {
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: "http://localhost:8000/api/:path*",
          },
        ];
      },
    };

export default nextConfig;
