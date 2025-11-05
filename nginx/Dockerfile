# Use the official Nginx image
FROM nginx:1.25-alpine

# Remove the default Nginx configuration file
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom nginx.conf
COPY nginx.conf /etc/nginx/conf.d/