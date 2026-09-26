# syntax=docker/dockerfile:1.7
# ---------- build stage: Node toolchain, never reaches the final image ----------
FROM node:22.12.0-alpine3.20 AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# ---------- serve stage: static files + nginx only ----------
FROM nginx:1.31.0-alpine AS runtime
# Upstream for the /api proxy. Overridable per environment; nothing is baked into the JS bundle.
ENV BACKEND_UPSTREAM=http://backend:8000 \
    APP_ENVIRONMENT=production
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.d/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
COPY --from=build /src/dist /usr/share/nginx/html
# Non-root: nginx user (uid 101) owns only what it must write at start-up.
RUN apk update && apk upgrade --no-cache \
 && chmod +x /docker-entrypoint.d/40-runtime-config.sh \
 && touch /usr/share/nginx/html/config.js \
 && rm -f /etc/nginx/conf.d/default.conf \
 && chown -R 101:101 /usr/share/nginx/html/config.js /etc/nginx/conf.d
USER 101
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
