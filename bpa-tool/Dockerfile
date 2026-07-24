FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY server.js ./
COPY public ./public
ENV PORT=4021
EXPOSE 4021
CMD ["node", "server.js"]
