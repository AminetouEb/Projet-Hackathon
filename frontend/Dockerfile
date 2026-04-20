# Stage 1: Build
FROM node:22-alpine AS build
WORKDIR /app
RUN npm install -g @angular/cli@21.2.7
COPY package*.json ./
RUN npm install
COPY . .
# Force explicit output path so Stage 2 copy is stable.
RUN ng build --configuration production 

# Stage 2: Nginx
FROM nginx:alpine
# Match the Angular 21 output path
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY default.conf.template /etc/nginx/templates/default.conf.template
RUN rm -rf /etc/nginx/conf.d/default.conf
EXPOSE 80