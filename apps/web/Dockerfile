FROM node:22-slim

WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
COPY assets ../assets
ENV VITE_API_BASE_URL=http://localhost:8000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
