#!/bin/bash

set -e # bei Fehler exit

SCRIPTPATHthis="$( cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 ; /bin/pwd -P )"
cd "$SCRIPTPATHthis"

docker rm paperless-overdue

docker compose build

echo -e "\nTest-Start with 'compose up' (use CTRL + c (or exit terminal) to stop): "
docker compose up 
echo -e "\nUse 'compose up -d' to run independent from Terminal (or start the container in he Synology Container Manager)"
