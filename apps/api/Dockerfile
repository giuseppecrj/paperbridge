FROM oven/bun:1.3.14-debian@sha256:9dba1a1b43ce28c9d7931bfc4eb00feb63b0114720a0277a8f939ae4dfc9db6f AS production-dependencies
WORKDIR /app
COPY package.json bun.lock ./
COPY apps/api/package.json apps/api/package.json
COPY packages/protocol/package.json packages/protocol/package.json
RUN bun install --frozen-lockfile --production

FROM oven/bun:1.3.14-debian@sha256:9dba1a1b43ce28c9d7931bfc4eb00feb63b0114720a0277a8f939ae4dfc9db6f AS build
WORKDIR /app
COPY package.json bun.lock ./
COPY apps/api/package.json apps/api/package.json
COPY packages/protocol/package.json packages/protocol/package.json
RUN bun install --frozen-lockfile
COPY apps/api/src apps/api/src
COPY packages/protocol/src packages/protocol/src
COPY packages/protocol/schemas packages/protocol/schemas
RUN bun run --filter @paperbridge/api build

FROM node:26.3.0-bookworm-slim@sha256:3fe807a03a4436e7bc76b7e84e6861899cd75c9028ae99bc00581940141ae150 AS runtime
ENV NODE_ENV=production
WORKDIR /app/apps/api
COPY --from=production-dependencies --chown=node:node /app/node_modules /app/node_modules
COPY --from=production-dependencies --chown=node:node /app/apps/api/node_modules ./node_modules
COPY --from=build --chown=node:node /app/apps/api/dist ./dist
USER node
EXPOSE 3000
CMD ["node", "dist/server.js"]
