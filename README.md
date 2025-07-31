## Descripción

**Estado: EN DESARROLLO**

Esta aplicación Python permite detectar Arduinos conectados (por USB y por red), escanear la red local, identificar dispositivos conectados (incluyendo dispositivos Modbus), listar información relevante de la red y de los dispositivos, y adquirir datos de todos ellos sin interferir en los procesos. Los datos recopilados se formatean en JSON y se envían a una base de datos PostgreSQL local y a un frontend desarrollado en Streamlit, desplegado en Streamlit Community Cloud.

**Frontend en producción:**
https://iotapp-jvwtoekeo73ruxn9mdhfnc.streamlit.app/

## Características principales
- Detección automática de Arduinos conectados por USB y por red.
- Escaneo de red para identificar dispositivos activos.
- Detección y monitoreo de dispositivos Modbus.
- Adquisición pasiva de datos de todos los dispositivos.
- Formateo de datos en JSON.
- Almacenamiento eficiente en PostgreSQL.
- Visualización de datos en tiempo real con Streamlit.

## Instrucciones de instalación y pruebas locales

### 1. Clonar el repositorio

```powershell
git clone https://github.com/Denniels/iot_streamlit.git
cd iot_streamlit/iot_streamlit
```

### 2. Crear el entorno virtual

```powershell
python -m venv .iot_streamlit
.\.iot_streamlit\Scripts\Activate
```

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación para pruebas locales

```powershell
python main.py
```
---
> Asegúrate de tener conectados el Arduino USB y el Arduino Ethernet en la red local antes de ejecutar la app para pruebas.



## Estructura de archivos y directorios

```
├── .iot_streamlit/                # Entorno virtual
├── arduino/
│   ├── arduino_ethernet_server.ino
│   ├── arduino_ethernet_server/   # Código Arduino Ethernet
│   │   └── arduino_ethernet_server.ino
│   ├── arduino_usb_sensor/        # Código Arduino USB
│   │   └── arduino_usb_sensor.ino
│   └── CONEXIONES.md
├── backend/
│   ├── __init__.py
│   ├── api.py
│   ├── arduino_detector.py
│   ├── config.py
│   ├── data_acquisition.py
│   ├── db_writer.py
│   ├── device_scanner.py
│   ├── modbus_scanner.py
│   ├── network_scanner.py
│   ├── postgres_client.py
│   ├── service_status.py
│   ├── sqlite_client.py
│   └── __pycache__/
├── database/
│   └── schema.sql
├── dev/
│   ├── requirements_cloud.txt
│   └── requirements_local.txt
├── docs/
│   ├── INSTALL.md
│   ├── JETSON_NANO_UPGRADE.md
│   ├── PROJECT_STATUS.md
│   ├── README_JETSON_NANO.md
│   ├── README_JETSON_NANO_DEV.md
│   ├── device_scan_20250724_002830.md
│   └── network_scan_report.md
├── frontend/
│   ├── app.py
│   ├── pipeline_iot.svg
│   └── # Code Citations.md
├── logs/
│   ├── acquire_data.log
│   ├── iot_backend.log
│   ├── start_cloudflare.log
│   └── sync_local_db.log
├── test/
│   ├── __init__.py
│   ├── api_flask.py
│   ├── arduino_diagnostic.py
│   ├── check_local_postgres.py
│   ├── device_scan.py
│   ├── diagnose_arduino.py
│   ├── network_scan.py
│   ├── network_scan_win.py
│   ├── test_arduino_connection.py
│   ├── test_arduino_ethernet_quick.py
│   ├── test_db_connection.py
│   ├── test_ethernet_arduino.py
│   ├── test_ethernet_detection.py
│   ├── test_ingesta_arduino.py
│   ├── test_lectura_arduino_usb.py
│   ├── test_localtunnel_write.py
│   ├── test_supabase_query.py
│   ├── test_supabase_reset.py
│   └── test_sync_supabase.py
├── acquire_data.py
├── acquire_data.service
├── api_flask.py
├── arduino_diagnostic.py
├── backend_api.service
├── cloudflared.deb
├── db_writer.py
├── dev_roadmap.md
├── diagnose_arduino.py
├── docker-compose.yml
├── Dockerfile
├── inicializacion_servicios_jetson.md
├── iot_local.db
├── main.py
├── requirements.txt
├── secrets.toml
├── secrets_tunnel.toml
├── setup_postgres.sh
├── start_cloudflare.py
├── start_cloudflare.service
├── start_cloudflare_py.service
├── sync_local_db.py
├── sync_local_db.service
└── README.md
```



## Diagrama de la base de datos local (PostgreSQL)

```mermaid
erDiagram
    DEVICES {
        SERIAL id PK
        VARCHAR device_id UNIQUE
        VARCHAR device_type
        VARCHAR name
        INET ip_address
        INTEGER port
        VARCHAR status
        TIMESTAMPTZ last_seen
        JSONB metadata
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }
    SENSOR_DATA {
        SERIAL id PK
        VARCHAR device_id FK
        VARCHAR sensor_type
        NUMERIC value
        VARCHAR unit
        JSONB raw_data
        TIMESTAMPTZ timestamp
        TIMESTAMPTZ created_at
    }
    SYSTEM_EVENTS {
        SERIAL id PK
        VARCHAR event_type
        VARCHAR device_id
        TEXT message
        JSONB metadata
        TIMESTAMPTZ timestamp
    }
    DEVICES ||--o{ SENSOR_DATA : "tiene"
    DEVICES ||--o{ SYSTEM_EVENTS : "genera"
```

---


## Principales avances y funcionalidades

- Detección automática de Arduinos USB y Ethernet.
- Escaneo de red y monitoreo de dispositivos Modbus.
- Backend robusto en Jetson Nano (servicios systemd, dockerizable).
- API RESTful para consulta y monitoreo desde el frontend.
- Visualización avanzada en Streamlit Cloud (gráficos, métricas, semáforo de servicios, pipeline SVG, selector de rango temporal, etc).
- Sincronización automática de la URL pública del backend (Cloudflare Tunnel) en el frontend.
- Documentación y scripts para despliegue y mantenimiento.

## Requisitos

- Python 3.8+
- PostgreSQL local
- Streamlit
- Docker (opcional, para despliegue final)
- Bibliotecas: pyserial, python-modbus, psycopg2, requests, plotly, etc.

---

Este README proporciona una visión general, estructura, flujo de datos y proceso de despliegue para tu proyecto IoT con Python, Arduinos, PostgreSQL y Streamlit. El sistema está en desarrollo activo y se recomienda revisar el roadmap (`dev_roadmap.md`) para conocer el estado y prioridades actuales.

## Subir la base de datos PostgreSQL a Supabase

Supabase es una plataforma que ofrece PostgreSQL como servicio en la nube. Puedes migrar tu base de datos local a Supabase siguiendo estos pasos:

### 1. Crear un proyecto en Supabase
- Regístrate en https://supabase.com/ y crea un nuevo proyecto.
- Obtén las credenciales de conexión (host, puerto, usuario, contraseña, base de datos) desde la sección "Project Settings > Database".

### 2. Exportar tu base de datos local
En tu entorno local, exporta el esquema y los datos de tu base de datos PostgreSQL:

```sh
pg_dump -U TU_USUARIO -h localhost -p 5432 -d TU_BD -F c -b -v -f backup_db.dump
```
O para solo el esquema:
```sh
pg_dump -U TU_USUARIO -h localhost -p 5432 -d TU_BD -s -f schema.sql
```

### 3. Importar el backup a Supabase
Puedes restaurar el backup usando `pg_restore` o importar el SQL desde la consola de Supabase:

**Con pg_restore:**
```sh
pg_restore --no-owner -h <host_supabase> -U <usuario_supabase> -d <bd_supabase> -p 5432 backup_db.dump
```
**Con psql (para archivos .sql):**
```sh
psql -h <host_supabase> -U <usuario_supabase> -d <bd_supabase> -f schema.sql
```

> Nota: Debes habilitar el acceso externo a la base de datos en la configuración de Supabase y permitir tu IP temporalmente.

### 4. Actualizar la configuración de conexión en tu app
Modifica las variables de entorno o el archivo de configuración de tu backend para que apunten a la base de datos de Supabase.