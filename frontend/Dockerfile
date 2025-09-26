# Frontend Dockerfile (build React app, serve via Nginx)

FROM node:18-bullseye-slim AS build
WORKDIR /app

# Install deps
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Build
COPY frontend/ ./
# Allow overriding API URL at build time if needed
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=${REACT_APP_API_URL}
RUN npm run build

FROM nginx:1.27-alpine AS runtime
WORKDIR /usr/share/nginx/html

# Copy build output
COPY --from=build /app/build ./

# Replace default Nginx site with SPA-friendly config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
