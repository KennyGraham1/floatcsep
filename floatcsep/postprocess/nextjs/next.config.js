/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // `floatcsep view` builds into its own directory (see server.py) so that a
  // development server never mixes its output with the production build.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // The dashboard is its own project, even inside the floatCSEP repository.
  outputFileTracingRoot: __dirname,
  // Result figures are local files served as-is; the image optimizer is unused.
  images: { unoptimized: true },
  eslint: { dirs: ['app', 'components', 'hooks', 'lib'] },
};

module.exports = nextConfig;
