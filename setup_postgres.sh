#!/bin/bash
# Script para inicializar PostgreSQL para IoT Streamlit

# Crear base de datos y usuario
sudo -u postgres psql <<EOF
CREATE DATABASE iot_db;
CREATE USER iot_user WITH PASSWORD 'iot_password';
GRANT ALL PRIVILEGES ON DATABASE iot_db TO iot_user;
EOF

# Cargar el esquema SQL
sudo -u postgres psql -d iot_db -f database/schema.sql

echo "Base de datos y usuario creados, esquema cargado."

echo "Si necesitas acceso a los puertos USB/TTY, ejecuta:"
echo "sudo usermod -a -G dialout $USER"
echo "Luego cierra sesión y vuelve a entrar para aplicar los cambios."
