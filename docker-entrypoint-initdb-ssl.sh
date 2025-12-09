#!/bin/bash
# Fix SSL certificate permissions on container startup

if [ -f /var/lib/postgresql/ssl/server.key ]; then
    chmod 600 /var/lib/postgresql/ssl/server.key
    chmod 644 /var/lib/postgresql/ssl/server.crt
    echo "SSL certificate permissions fixed"
fi

exec "$@"

