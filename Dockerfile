FROM ghcr.io/dockur/windows

ENV VERSION="11"
ENV USERNAME="user"
ENV PASSWORD="pass"

# Auto-run setup script after first Windows boot
COPY docker_setup.bat /oem/docker_setup.bat

# Project files are mounted via docker-compose volume: ./:/shared
# accessible inside Windows VM as \\host.lan\Data\
