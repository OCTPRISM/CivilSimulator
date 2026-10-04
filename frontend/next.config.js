/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-pageflip mutates the DOM directly and is not StrictMode-safe.
  reactStrictMode: false,
  async rewrites() {
    const target = process.env.BACKEND_URL || "http://localhost:8001";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
