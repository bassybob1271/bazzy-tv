FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_URL
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL
ARG NEXT_PUBLIC_STRIPE_PK
ARG NEXT_PUBLIC_BAZZY_LIVE_URL=https://live.bazzy.tv
ARG NEXT_PUBLIC_BAZZYBOX_URL=https://box.bazzy.tv
ENV NEXT_PUBLIC_BAZZY_LIVE_URL=$NEXT_PUBLIC_BAZZY_LIVE_URL
ENV NEXT_PUBLIC_BAZZYBOX_URL=$NEXT_PUBLIC_BAZZYBOX_URL
ARG NEXT_PUBLIC_STRIPE_CONNECT_CLIENT_ID
ENV NEXT_PUBLIC_STRIPE_CONNECT_CLIENT_ID=$NEXT_PUBLIC_STRIPE_CONNECT_CLIENT_ID
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_STRIPE_PK=$NEXT_PUBLIC_STRIPE_PK
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
ENV PORT 3000
CMD ["node", "server.js"]
