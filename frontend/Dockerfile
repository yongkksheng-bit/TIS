# =======================
# Stage 1: Builder
# =======================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first (for dependency caching)
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --prefer-offline

# Copy source
COPY . .

# Build arguments for API configuration
ARG VITE_USE_MOCK=false
ARG VITE_API_BASE_URL=/api

# Set environment for build
ENV VITE_USE_MOCK=$VITE_USE_MOCK
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build production assets
RUN npm run build

# =======================
# Stage 2: Nginx Server
# =======================
FROM nginx:alpine AS runner

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx runs as nginx user by default (non-root)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]