FROM node:18-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev
COPY server.js ./
ENV PORT=9000
EXPOSE 9000
CMD ["node", "server.js"]
