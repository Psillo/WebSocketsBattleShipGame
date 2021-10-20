#!/bin/sh

if [ -n "$1" ]
then
while [ -n "$1" ]
do
case "$1" in
-app_port) sed -i -e "s/\(APP_PORT=\).*/\1$2/" .env && docker-compose --env-file .env up --detach --build && echo PORT $2 && break ;;
esac
done
else
docker-compose --env-file .env up --detach --build
fi