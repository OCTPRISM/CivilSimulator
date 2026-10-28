/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-pageflip mutates the DOM directly and is not StrictMode-safe.
  reactStrictMode: false,
  // public/models holds ~1.8k GLBs; watching them exhausts macOS file descriptors
  // and leaves `next dev` hung on first compile (EMFILE).
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        ...config.watchOptions,
        ignored: [
          "**/.git/**",
          "**/node_modules/**",
          "**/.next/**",
          "**/public/models/**",
        ],
      };
    }
    return config;
  },
  async rewrites() {
    // Default backend matches README / uvicorn --port 8000 (R0-6).
    const target = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
