# TÜMEN AI Data Science Platform — Frontend
#
# Multi-stage build:
#   1. node:22-alpine  — install deps + vite build
#   2. nginx:alpine    — serve static files + proxy API requests
#
# Build:  docker build -f frontend/Dockerfile -t tumen-frontend:latest .
# Run:    docker run -p 3000:80 tumen-frontend:latest

# ---- Builder ----
FROM node:22-alpine AS builder

WORKDIR /build

# Copy dependency manifests
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-fund --no-audit

# Copy source
COPY frontend/ .

# Build
RUN npm run build

# ---- Runtime ----
FROM nginx:1.27-alpine

# Copy built assets
COPY --from=builder /build/dist /usr/share/nginx/html

# Copy nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Health check: nginx returns 200 on /
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
