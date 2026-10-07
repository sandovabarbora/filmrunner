// Loaded for every test file (see vite.config.ts `test.setupFiles`). Cheap to import in
// the default "node" environment too — it only extends `expect`, never touches the DOM
// until a jest-dom matcher actually runs, which only happens in a jsdom-environment test.
import "@testing-library/jest-dom/vitest";
