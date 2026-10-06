/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-pageflip mutates the DOM directly and is not StrictMode-safe.
  reactStrictMode: false,
  async rewrites() {
    // Default backend matches README / uvicorn --port 8000 (R0-6).
    const target = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
