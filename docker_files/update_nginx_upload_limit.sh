#!/bin/bash

# Script to update Nginx configuration to fix 413 Request Entity Too Large error
# This script adds client_max_body_size to Nginx configuration files

NGINX_CONF_DIR="/data/global/conf/nginx/conf"
CLIENT_MAX_BODY_SIZE="10M"

echo "Updating Nginx configuration to allow larger file uploads..."
echo "Configuration directory: $NGINX_CONF_DIR"
echo "Setting client_max_body_size to: $CLIENT_MAX_BODY_SIZE"
echo ""

# Check if directory exists
if [ ! -d "$NGINX_CONF_DIR" ]; then
    echo "Error: Nginx configuration directory not found: $NGINX_CONF_DIR"
    exit 1
fi

# Find all .conf files in the directory
CONF_FILES=$(find "$NGINX_CONF_DIR" -name "*.conf" -type f)

if [ -z "$CONF_FILES" ]; then
    echo "Warning: No .conf files found in $NGINX_CONF_DIR"
    exit 1
fi

# Process each configuration file
for conf_file in $CONF_FILES; do
    echo "Processing: $conf_file"
    
    # Check if client_max_body_size already exists
    if grep -q "client_max_body_size" "$conf_file"; then
        echo "  - client_max_body_size already exists, updating value..."
        # Update existing value (works for most cases)
        sed -i "s/client_max_body_size.*/client_max_body_size $CLIENT_MAX_BODY_SIZE;/" "$conf_file"
    else
        echo "  - Adding client_max_body_size to server blocks..."
        
        # Add to each server block that doesn't have it
        # This uses a more complex sed pattern to add after server { line
        awk -v size="$CLIENT_MAX_BODY_SIZE" '
        /^[[:space:]]*server[[:space:]]*\{/ {
            print
            print "    client_max_body_size " size ";"
            next
        }
        { print }
        ' "$conf_file" > "$conf_file.tmp" && mv "$conf_file.tmp" "$conf_file"
    fi
    
    echo "  ✓ Updated: $conf_file"
done

echo ""
echo "Configuration updated successfully!"
echo ""
echo "Next steps:"
echo "1. Test Nginx configuration: nginx -t"
echo "2. If test passes, reload Nginx: nginx -s reload"
echo "   Or if using Docker: docker exec <nginx_container> nginx -s reload"
echo ""
echo "Manual verification:"
echo "  Check that 'client_max_body_size $CLIENT_MAX_BODY_SIZE;' appears in your server blocks"
