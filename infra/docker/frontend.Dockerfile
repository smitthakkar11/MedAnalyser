# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# MedAnalyser frontend image.
#
# Builds the static bundle, then serves it from nginx. nginx also proxies /api
# to the backend, so the browser stays same-origin and no CORS config or
# baked-in API hostname is required.
# ---------------------------------------------------------------------------

FROM node:22-alpine AS builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Empty base URL => relative /api requests, resolved by the nginx proxy below.
ENV VITE_API_BASE_URL=""
RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY infra/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
