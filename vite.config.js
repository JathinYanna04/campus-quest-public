import { defineConfig } from 'vite';

export default defineConfig({
  // Relative base so the same build works at a GitHub Pages subpath
  // (user.github.io/campus-quest/) and at a Vercel domain root.
  base: './',
  build: {
    outDir: 'dist',
    // Phaser alone is ~1.2 MB minified; don't warn about it on every build.
    chunkSizeWarningLimit: 1600,
  },
});
