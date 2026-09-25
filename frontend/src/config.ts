/** Runtime (not build-time) configuration, read from window.__CIVICPULSE_CONFIG__ set by /config.js. */
export interface RuntimeConfig {
  environment: string;
  apiBase: string;
}

declare global {
  interface Window {
    __CIVICPULSE_CONFIG__?: Partial<RuntimeConfig>;
  }
}

export function getConfig(): RuntimeConfig {
  const c = window.__CIVICPULSE_CONFIG__ ?? {};
  return {
    environment: c.environment ?? "unknown",
    // Relative by default: nginx proxies /api, so the bundle never needs the backend's address.
    apiBase: (c.apiBase ?? "/api").replace(/\/$/, ""),
  };
}
