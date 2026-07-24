FROM node:20-slim AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
# Vite inlines VITE_* vars into the built JS at compile time, so they have
# to be passed as build args (not runtime env vars) - see docker-compose.yml.
ARG VITE_ROOT_DOMAIN=
ARG VITE_GOOGLE_CLIENT_ID=
ARG VITE_API_BASE=
ENV VITE_ROOT_DOMAIN=$VITE_ROOT_DOMAIN \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
