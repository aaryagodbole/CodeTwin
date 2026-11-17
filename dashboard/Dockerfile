# CodeTwin dashboard for self-hosting (compose.yaml): static export served by nginx.
# DATA_MODE: "demo" (bundled snapshot) or "live" (reads the API at NEXT_PUBLIC_API_URL).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG DATA_MODE=demo
ARG API_URL=""
ENV NEXT_PUBLIC_DATA_MODE=$DATA_MODE NEXT_PUBLIC_API_URL=$API_URL NEXT_TELEMETRY_DISABLED=1
RUN npx next build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/out /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
