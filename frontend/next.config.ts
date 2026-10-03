import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
    // same origin so the guest cookie works without cors
    async rewrites() {
        return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
    },
    experimental: {
        proxyTimeout: 5 * 60 * 1000,
    },
};

export default nextConfig;
