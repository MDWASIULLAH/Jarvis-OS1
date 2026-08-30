import type { NextConfig } from "next";
const config: NextConfig = { async rewrites(){ return [{ source:"/backend/:path*", destination:`${process.env.JARVIS_BACKEND_URL ?? "http://localhost:8000"}/:path*` }]; } };
export default config;
