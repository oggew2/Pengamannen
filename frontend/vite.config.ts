import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'child_process'

// Get git info at build time (from git or env vars)
const getGitInfo = () => {
  // Try env vars first (set by Docker build)
  if (process.env.VITE_GIT_COMMIT && process.env.VITE_GIT_COMMIT !== 'unknown') {
    return {
      commitHash: process.env.VITE_GIT_COMMIT,
      commitDate: process.env.VITE_GIT_DATE || new Date().toISOString(),
    }
  }
  // Fall back to git commands (local dev)
  try {
    const commitHash = execSync('git rev-parse --short HEAD').toString().trim()
    const commitDate = execSync('git log -1 --format=%ci').toString().trim()
    return { commitHash, commitDate }
  } catch {
    return { commitHash: 'unknown', commitDate: new Date().toISOString() }
  }
}

const gitInfo = getGitInfo()
const buildTime = process.env.VITE_BUILD_TIME || new Date().toISOString()

export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_TIME__: JSON.stringify(buildTime),
    __GIT_COMMIT__: JSON.stringify(gitInfo.commitHash),
    __GIT_DATE__: JSON.stringify(gitInfo.commitDate),
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['recharts']
        }
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})
