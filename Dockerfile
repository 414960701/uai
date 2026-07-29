# syntax=docker/dockerfile:1.7

FROM node:22.13-alpine AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

FROM dependencies AS build
COPY . .
# Local/container builds do not require a Sites project. Keep the build portable
# when the deployment-owned hosting file is intentionally absent from source.
RUN mkdir -p .openai && \
    if [ ! -f .openai/hosting.json ]; then \
      printf '%s\n' '{"d1":null,"r2":null}' > .openai/hosting.json; \
    fi && \
    npm run build

FROM node:22.13-alpine AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    WRANGLER_WRITE_LOGS=false

RUN addgroup -S -g 10001 uai && \
    adduser -S -D -H -u 10001 -G uai uai

# vinext is currently a development dependency but also provides the production
# server binary, so retain the lockfile-resolved dependency tree in this image.
COPY --from=build --chown=uai:uai /app/package.json /app/package-lock.json ./
COPY --from=build --chown=uai:uai /app/node_modules ./node_modules
COPY --from=build --chown=uai:uai /app/dist ./dist

USER uai
EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
