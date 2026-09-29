# Multi-stage build: compile the Vite SPA, then serve the static output with nginx.
#
# The dev server (vite, port 5173) is not used in Kubernetes. nginx serves the
# built assets and reverse-proxies /api to the backend Service, which keeps the
# browser on a single origin and means no CORS configuration is required.

FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked in at build time. `/api` is proxied by nginx (see nginx.conf), so the
# browser only ever talks to the frontend origin.
ARG VITE_API_URL=/api
RUN printf 'VITE_API_URL=%s\n' "$VITE_API_URL" > .env.production

RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
