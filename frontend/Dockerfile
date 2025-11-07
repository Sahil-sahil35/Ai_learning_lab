FROM node:20-alpine

WORKDIR /app

# Install additional packages for rollup
RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    libc6-compat

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]