# CHINA
FROM node:18-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* ./

ARG NPM_REGISTRY=https://registry.npmmirror.com
ENV npm_config_registry=${NPM_REGISTRY}
ENV npm_config_audit=false
ENV npm_config_fund=false
ENV npm_config_progress=false

RUN --mount=type=cache,target=/root/.npm \
    npm ci

FROM node:18-alpine AS build
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
