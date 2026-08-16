# Base dependencies stage
FROM node:20-slim AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Development stage (runs npm run dev with fast hot-reloading)
FROM node:20-slim AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV NODE_ENV=development
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]

# Production builder stage (runs next build)
FROM deps AS builder
COPY . .
RUN npm run build

# Production runner stage (minimal, runs next start)
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]
