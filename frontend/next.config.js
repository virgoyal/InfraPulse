/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  transpilePackages: ["leaflet", "react-leaflet"],
  images: { unoptimized: true },
};

module.exports = nextConfig;
