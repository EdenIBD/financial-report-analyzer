import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // build lean pentru Docker (copiaza doar ce e nevoie sa ruleze, nu tot node_modules)
};

export default nextConfig;
