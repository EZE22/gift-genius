# Image for the Gift Genius web front end. Plain code: a two stage build.
# Stage 1 uses Node to turn the React source into plain static files. Stage 2
# serves only those files with nginx. The finished image contains no Node, no
# source code and no npm packages, so it is small and has little to attack.

# ---- Stage 1: build the static files ----
# One pinned Node version. The packages need 22.12 or newer.
FROM node:22-slim AS build
WORKDIR /app

# Copy ONLY the package files first and install. Docker caches each step, so
# this step reruns only when the packages change, not on every code edit.
# "npm ci" installs exactly what package-lock.json says.
COPY package.json package-lock.json ./
RUN npm ci

# Now the source. "npm run build" type checks, then writes the finished
# files to /app/dist.
COPY . .
RUN npm run build

# ---- Stage 2: serve the files ----
# The "unprivileged" nginx image runs as a normal user and listens on 8080,
# because a normal user cannot bind port 80.
FROM nginxinc/nginx-unprivileged:1.27-alpine

# Our routing rules replace the image's default site.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Take only the finished files from stage 1.
COPY --from=build /app/dist /usr/share/nginx/html

# Documentation only: "docker run -p" publishes the port.
EXPOSE 8080
