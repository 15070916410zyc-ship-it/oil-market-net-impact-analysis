import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    coverage: {
      include: ["src/lib/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    },
  },
});
