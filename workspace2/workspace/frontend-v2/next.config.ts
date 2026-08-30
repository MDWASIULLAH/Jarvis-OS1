import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  // `appIsrStatus` / `buildActivity` were removed in Next 15 and only produced
  // an "Invalid next.config.ts options detected" warning on every dev boot.
  devIndicators: false,
};

export default config;
