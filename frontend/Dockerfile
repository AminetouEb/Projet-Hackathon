# ---------- BUILD STAGE ----------
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund

COPY . .

# build Angular en production
RUN npm run build

# ---------- PRODUCTION STAGE ----------
FROM nginx:alpine

# nettoyer le dossier nginx
RUN rm -rf /usr/share/nginx/html/*

# ⚠️ adapter selon le nom du projet Angular
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]