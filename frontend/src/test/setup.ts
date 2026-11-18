import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); });

// jsdom lacks these browser APIs used by framer-motion / recharts / theme detection.
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({ matches: false, media: query, onchange: null, addEventListener: () => {}, removeEventListener: () => {}, addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false }),
});
class IO { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } }
(globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = IO;
window.scrollTo = () => {};
Element.prototype.scrollIntoView = () => {};
