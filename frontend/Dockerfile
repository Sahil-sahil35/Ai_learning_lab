# Use a Node.js 18 base image
FROM node:20-alpine

# Set the working directory
WORKDIR /app

# Copy package.json and package-lock.json first
# This leverages Docker's layer caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY . .

# Expose the Vite port
EXPOSE 5173

# Run the Vite development server, listening on all interfaces
# This is required for it to be accessible from other Docker containers
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]