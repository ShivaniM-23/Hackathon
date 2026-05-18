FROM node:20-alpine AS base

# ── Stage 1: Install dependencies ─────────────────────────────────────────────
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── Stage 2: Build the Next.js app ────────────────────────────────────────────
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# These are needed at BUILD TIME for Next.js to inline them
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# ── Stage 3: Production runner ────────────────────────────────────────────────
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

# Copy standalone output
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
