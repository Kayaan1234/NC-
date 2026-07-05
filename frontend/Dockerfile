# Web image for NC++: builds the React/Vite bundle and serves it with nginx,
# which also reverse-proxies the API prefixes so the browser sees ONE origin.
# Build context is the REPO ROOT (needs frontend/ AND docker/nginx.conf.template):
#   docker build -f frontend/Dockerfile -t ncplusplus-web .

# ---- build the static bundle. VITE_API_URL is baked in HERE, at BUILD time.
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# "" => the SPA calls /auth, /users, ... on its OWN origin (same-origin nginx).
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- serve with nginx
FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
# PORT and BACKEND_URL are substituted into the template at container start.
# The FILTER restricts envsubst to just these two names so nginx's own $host,
# $scheme, ... runtime variables are left untouched.
ENV PORT=8080 \
    BACKEND_URL=http://backend:8000 \
    NGINX_ENVSUBST_FILTER="PORT|BACKEND_URL"
EXPOSE 8080
# (the base nginx image's entrypoint runs envsubst on templates, then starts nginx)
