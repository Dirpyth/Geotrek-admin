#!/usr/bin/env bash

# TODO: add a test
# TODO: allow psql from 172.16.0.0/12
# TODO: don't apt update if no apt install is required
# TODO: configure cors
# TODO: migration from existing installation
# TODO: fix Geotrek version

function progress () {
    set +x
    exec 2>&4
    echo -e "\e[$1m\e[1m$2\e[0m" >&2
    exec 2>&1
    set -x
}

trap "progress 91 'Installation failed. Please check install.log file.'" ERR

# Setup logging
touch install.log
chmod 600 install.log  # Hide passwords to others users
exec 3>&1 4>&2
exec 1>> install.log 2>&1

set -ex

# Get version
VERSION=$(cat VERSION)
progress 97 "Install Geotrek-admin $VERSION $(date)"

# Check user is not root
if [ "$(id -u)" == "0" ]; then
    progress 91 "For security reasons, this script must NOT be run as root"
    exit 1
fi

# Check Ubuntu release
if [ "$(lsb_release -is)" != "Ubuntu" ]; then
    progress 91 "Only Ubuntu distribution is supported by this script"
    exit 1
fi
if [ "$(lsb_release -rs)" == "16.04" ]; then
    progress 37 "Ubuntu 16.04 LTS detected"
    psql_version=9.5
    pgis_version=2.2
elif [ "$(lsb_release -rs)" == "18.04" ]; then
    progress 37 "Ubuntu 18.04 LTS detected"
    psql_version=10
    pgis_version=2.4
elif [ "$(lsb_release -rs)" == "19.10" ]; then
    progress 93 "Ubuntu 19.10 detected. This distribution has no long term support (LTS) and should not be used in production"
    psql_version=11
    pgis_version=2.5
else
    progress 91 "Only Ubuntu 16.04 LTS and 18.04 LTS are supported by this script"
    exit 1
fi

# Update packages list
progress 97 "Update packages list"
sudo apt-get update

# Install packages
progress 97 "Install packages"
sudo apt-get install -y -q \
    dialog \
    docker.io \
    docker-compose \
    nginx

if [ -z "$POSTGRES_HOST" ]; then
    sudo apt-get install -y -q \
        postgresql-$psql_version \
        postgresql-$psql_version-postgis-$pgis_version
fi

# Create config file
if [ -f .env ]; then
    progress 97 "Found existing .env configuration file"
else
    progress 97 "Create .env configuration file"
    cp .env-prod.dist .env
    echo "USER_ID=$(id -u)" >> .env
    echo "GROUP_ID=$(id -g)" >> .env
    chmod 600 .env
fi
source .env

ALLOWED_HOSTS=$(dialog --no-cancel --inputbox "Geotrek-admin server name (domain)" 7 70 "$ALLOWED_HOSTS" 2>&1 1>&3)
POSTGRES_HOST=$(dialog --no-cancel --inputbox "PostgreSQL host (leave empty for local host)" 7 70 "$POSTGRES_HOST" 2>&1 1>&3)
[ "$POSTGRES_HOST" = "localhost" ] && POSTGRES_HOST=""
POSTGRES_PORT=$(dialog --no-cancel --inputbox "PostgreSQL port" 7 70 "$POSTGRES_PORT" 2>&1 1>&3)
POSTGRES_USER=$(dialog --no-cancel --inputbox "PostgreSQL user" 7 70 "$POSTGRES_USER" 2>&1 1>&3)
POSTGRES_PASSWORD=$(dialog --no-cancel --inputbox "PostgreSQL password" 7 70 "$POSTGRES_PASSWORD" 2>&1 1>&3)
POSTGRES_DB=$(dialog --no-cancel --inputbox "PostgreSQL database" 7 70 "$POSTGRES_DB" 2>&1 1>&3)
sed -i "s/^GEOTREK_VERSION=.*$/GEOTREK_VERSION=$VERSION/" .env
sed -i "s/^ALLOWED_HOSTS=.*$/ALLOWED_HOSTS=$ALLOWED_HOSTS/" .env
sed -i "s/^POSTGRES_HOST=.*$/POSTGRES_HOST=$POSTGRES_HOST/" .env
sed -i "s/^POSTGRES_PORT=.*$/POSTGRES_PORT=$POSTGRES_PORT/" .env
sed -i "s/^POSTGRES_USER=.*$/POSTGRES_USER=$POSTGRES_USER/" .env
sed -i "s/^POSTGRES_PASSWORD=.*$/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" .env
sed -i "s/^POSTGRES_DB=.*$/POSTGRES_DB=$POSTGRES_DB/" .env

# Create and read docker-compose.yml file
if [ -f docker-compose.yml ]; then
    progress 97 "Found existing docker-compose.yml configuration file"
else
    progress 97 "Create docker-compose.yml file"
    cp docker-compose-prod.yml docker-compose.yml
fi

# Create database user
if [ -n "$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER';")" ]; then
    progress 97 "Found existing $POSTGRES_USER database user"
else
    progress 97 "Create $POSTGRES_USER database user"
    sudo -u postgres psql -c "CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';"
fi

# Create database
if [ -n "$(sudo -u postgres psql -tAl | grep "^$POSTGRES_DB|")" ]; then
    progress 97 "Found existing $POSTGRES_DB database"
    fresh_db_install=false
else
    progress 97 "Create $POSTGRES_DB database"
    sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} ENCODING 'UTF8' OWNER ${POSTGRES_USER};"
    sudo -u postgres psql -c "CREATE EXTENSION postgis;" -d "${POSTGRES_DB}"
    fresh_db_install=true
fi

# Update (migrations, translations, permissions, statics)
progress 97 "Update database and ressource files"
mkdir -p var  # otherwise created by docker as root when bindind volume
docker-compose run --rm web update.sh

# Populate database with defaults
if $fresh_db_install; then
    progress 97 "Populate database with defaults"
    docker-compose run --rm web load_data.sh
fi

# Configure Geotrek service
echo "Configure Geotrek-admin service"
sudo tee /etc/systemd/system/geotrek.service > /dev/null << END
[Unit]
Description=Geotrek-admin
Requires=docker.service
After=docker.service

[Service]
TimeoutStartSec=0
TimeoutStopSec=30
Restart=always
RestartSec=10
WorkingDirectory=$PWD
ExecStartPre=-/usr/bin/docker-compose down
ExecStart=/usr/bin/docker-compose up
ExecStop=/usr/bin/docker-compose down

[Install]
WantedBy=multi-user.target
END
sudo systemctl daemon-reload
sudo systemctl enable geotrek

# Restart Geotrek-admin
progress 97 "Restart Geotrek-admin"
sudo service geotrek restart
# Configure nginx
progress 97 "Configure nginx"
sudo tee /etc/nginx/sites-available/geotrek > /dev/null << END
server {
    listen 80;
    listen [::]:80;
    server_name $ALLOWED_HOSTS;

    access_log /var/log/nginx/geotrek_access.log;
    error_log /var/log/nginx/geotrek_error.log;

    client_max_body_size 10M;

    add_header Access-Control-Allow-Origin *;

    location /static/ {
        expires 1d;
        alias $PWD/var/static/;
    }

    location /media/upload/ {
        expires 1d;
        alias $PWD/var/media/upload/;
    }

    location /media_secure/ {
        internal;
        expires 1d;
        alias $PWD/var/media/;
    }

    location / {
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_set_header X-Forwarded-Server \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header Host \$http_host;
        proxy_redirect off;

        keepalive_timeout 0;

        location ~ ^/api {
            proxy_pass http://127.0.0.1:$API_PORT;
            proxy_read_timeout 600s;
        }

        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_read_timeout 600s;
    }
}
END
sudo ln -sf /etc/nginx/sites-available/geotrek /etc/nginx/sites-enabled/geotrek

# Restart nginx
progress 97 "Restart nginx"
sudo nginx -t && sudo service nginx reload

# Done
progress 32 "Installation successful. Go to http://$ALLOWED_HOSTS"
