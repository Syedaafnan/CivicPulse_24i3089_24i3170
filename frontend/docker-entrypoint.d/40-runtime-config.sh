#!/bin/sh
# Generate /config.js from environment variables at container start, so ONE image
# runs unchanged in dev, CI and prod (build once, deploy many). No secrets here.
set -eu
esc() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
cat > /usr/share/nginx/html/config.js <<JS
window.__CIVICPULSE_CONFIG__ = { environment: "$(esc "${APP_ENVIRONMENT:-production}")", apiBase: "/api" };
JS
echo "runtime config written for environment=${APP_ENVIRONMENT:-production}"
