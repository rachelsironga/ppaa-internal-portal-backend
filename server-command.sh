#!/bin/bash
sudo docker network create ppaa-network
sudo mkdir -p /opt/ppaa-data/postgres
sudo chown -R 999:999 /opt/ppaa-data/postgres