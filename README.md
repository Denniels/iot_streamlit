## Descripción

Esta aplicación Python permite detectar Arduinos conectados (por USB y por red), escanear la red local, identificar dispositivos conectados (incluyendo dispositivos Modbus), listar información relevante de la red y de los dispositivos, y adquirir datos de todos ellos sin interferir en los procesos. Los datos recopilados se formatean en JSON y se envían a una base de datos PostgreSQL y a un frontend desarrollado en Streamlit, desplegado en Streamlit Community Cloud.

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
├── arduino/                       # Código de los Arduinos
│   ├── usb_arduino/               # Código para Arduino conectado por USB
│   │   └── usb_arduino.ino        
│   └── net_arduino/               # Código para Arduino conectado por red
│       └── net_arduino.ino        
├── backend/
│   ├── device_scanner.py          # Escaneo de red y detección de dispositivos
│   ├── arduino_detector.py        # Detección y comunicación con Arduinos
│   ├── modbus_scanner.py          # Detección y monitoreo de dispositivos Modbus
│   ├── data_acquisition.py        # Adquisición y formateo de datos
│   ├── db_writer.py               # Envío de datos a PostgreSQL/Supabase
│   └── api.py                     # API RESTful (FastAPI/Flask)
├── frontend/
│   └── app.py                     # Frontend Streamlit
├── database/
│   └── schema.sql                 # Esquema de la base de datos PostgreSQL
├── requirements_local.txt         # Dependencias para Jetson Nano
├── requirements_cloud.txt         # Dependencias para Streamlit Cloud
├── .env.local                     # Variables de entorno locales
├── .env.cloud                     # Variables de entorno cloud
├── README.md                      # Este archivo
└── main.py                        # Orquestador principal
```


## Pipeline y flujo de datos

```mermaid
flowchart LR
    subgraph Dispositivos
        A1[Arduino USB]
        A2[Arduino Ethernet]
        O[Otros dispositivos (PLC, variadores, etc.)]
    end
    subgraph Jetson Nano (Backend)
        B1[Captura y procesamiento de datos]
        B2[API RESTful (api.py)]
        B3[Cliente Supabase]
    end
    subgraph Supabase (PostgreSQL Cloud)
        S1[Base de datos centralizada]
    end
    subgraph Streamlit Community Cloud (Frontend)
        F1[Consulta periódica a Supabase y/o API]
        F2[Visualización de datos]
    end

    A1 --> B1
    A2 --> B1
    O  --> B1
    B1 --> B2
    B1 --> B3
    B3 --> S1
    F1 --> S1
    F1 --> B2
    F1 --> F2
```


```
┌──────────────────────┐        ┌──────────────────────────────┐        ┌──────────────────────────────┐        ┌──────────────────────────────────────────────┐
│  Dispositivos físicos│        │   Jetson Nano (Backend)      │        │      Supabase (Cloud)        │        │ Streamlit Community Cloud (Frontend)         │
│──────────────────────│        │------------------------------│        │-----------------------------│        │----------------------------------------------│
│ - Arduino USB        │  ───▶  │  Captura y procesamiento     │  ───▶  │  Base de datos centralizada  │  ───▶  │  Consulta periódica y visualización         │
│ - Arduino Ethernet   │  ───▶  │  de datos y envío a Supabase │        │                             │        │                                              │
│ - PLC, variadores... │  ───▶  │  (API RESTful: api.py)       │        │                             │        │                                              │
└──────────────────────┘        └──────────────────────────────┘        └──────────────────────────────┘        └──────────────────────────────────────────────┘
```

**Flujo:**
1. Los dispositivos físicos envían datos a la Jetson Nano.
2. La Jetson Nano procesa y sube los datos a Supabase y/o expone una API RESTful.
3. El frontend en Streamlit consulta periódicamente Supabase y/o la API para mostrar los datos al usuario.

**Ventajas:**
- Desacopla completamente backend y frontend.
- Permite escalabilidad y tolerancia a fallos.
- Facilita la seguridad y el acceso controlado a los datos.
- El frontend puede funcionar desde cualquier lugar con acceso a Supabase.

## Explicación del flujo de datos

1. **Dispositivos físicos** (Arduino USB, Arduino Ethernet, PLC, variadores, etc.) envían datos a la **Jetson Nano** mediante los protocolos soportados (USB, Ethernet, Modbus, etc.).
2. El **backend en la Jetson Nano** captura y procesa estos datos, formateándolos en JSON u otra estructura adecuada.
3. El backend almacena todos los datos directamente en **Supabase** (PostgreSQL en la nube) y/o los expone mediante una **API RESTful**.
4. El **frontend** (desplegado en Streamlit Community Cloud) consulta periódicamente Supabase y/o la API para obtener los datos más recientes.
5. El frontend visualiza y presenta los datos al usuario final, permitiendo monitoreo en tiempo real o casi real, sin necesidad de exponer la Jetson Nano a Internet ni abrir puertos adicionales.

## API RESTful recomendada para la comunicación Backend-Frontend

Se recomienda implementar una API RESTful en el backend (Jetson Nano) para exponer información relevante y permitir una integración flexible con el frontend. Esta API puede convivir con la estrategia de Supabase y ser consultada por el frontend para obtener datos en tiempo real, estado de dispositivos o ejecutar acciones.

### Ejemplo de endpoints sugeridos (FastAPI o Flask):

- `GET /devices` — Lista todos los dispositivos detectados y su estado.
- `GET /data/latest` — Devuelve los datos más recientes de todos los dispositivos.
- `GET /data/{device_id}` — Devuelve los datos de un dispositivo específico.
- `POST /command` — Permite enviar comandos a un dispositivo (opcional, para control remoto).

#### Ejemplo de estructura de FastAPI (backend/api.py):

```python
from fastapi import FastAPI
from typing import List

app = FastAPI()

@app.get("/devices")
def get_devices():
    # Lógica para listar dispositivos
    return [{"id": "arduino_usb", "status": "online"}, ...]

@app.get("/data/latest")
def get_latest_data():
    # Lógica para devolver los datos más recientes
    return [{"device_id": "arduino_usb", "value": 123, "timestamp": "..."}, ...]

@app.get("/data/{device_id}")
def get_device_data(device_id: str):
    # Lógica para devolver datos de un dispositivo específico
    return {"device_id": device_id, "values": [...]}

@app.post("/command")
def send_command(command: dict):
    # Lógica para enviar comandos a dispositivos
    return {"status": "ok"}
```

### Integración desde el frontend (Streamlit):

Puedes consultar la API desde Streamlit usando `requests`:

```python
import requests

response = requests.get("http://<ip_jetson>:8000/devices")
devices = response.json()
st.write(devices)
```

> Recuerda que para acceder a la API desde Streamlit Community Cloud, la Jetson Nano debe estar accesible desde Internet (no recomendado por seguridad) o exponer la API solo en redes privadas/VPN.

En la mayoría de los casos, la mejor opción es que el backend siga enviando los datos a Supabase y el frontend consulte Supabase, usando la API solo para funciones avanzadas o monitoreo en tiempo real dentro de la red local.

## Notas sobre los Arduinos
- `usb_arduino.ino`: Programa para Arduino conectado por USB, envía datos por serial.
- `net_arduino.ino`: Programa para Arduino conectado a la red, envía datos por TCP/UDP.


## Dockerización del Backend

El backend está preparado para ser dockerizado y ejecutarse en una Jetson Nano. El contenedor recopila datos de los Arduinos (USB y Ethernet) y detecta cualquier otro dispositivo conectado a la red, listando y adquiriendo datos de todos ellos de forma automática al iniciar el contenedor.

### Proceso de desarrollo y despliegue

1. **Desarrollo local (Windows):**
    - Desarrolla y prueba el backend y frontend en tu entorno local usando el entorno virtual `.iot_streamlit`.
    - Conecta el Arduino USB y el Arduino Ethernet para pruebas.
    - Asegúrate de que el backend detecta y adquiere datos de ambos Arduinos y de otros dispositivos en la red.

2. **Dockerización:**
    - Una vez finalizado el desarrollo, crea un `Dockerfile` en la carpeta `backend/` para contenerizar la aplicación.
    - El contenedor debe exponer los puertos necesarios y tener acceso al puerto USB para el Arduino y a la red local para el Arduino Ethernet y otros dispositivos.
    - El backend debe iniciar automáticamente la detección y adquisición de datos al levantar el contenedor.

3. **Despliegue en Jetson Nano:**
    - Sigue las instrucciones detalladas en [`README_JETSON_NANO.md`](./README_JETSON_NANO.md) para clonar el repositorio y ejecutar la app en la Jetson Nano.
    - Conecta el Arduino USB y asegúrate de que el Arduino Ethernet esté en la misma red antes de iniciar el contenedor Docker.

### Notas importantes
- El backend debe ser capaz de detectar cualquier dispositivo nuevo que se conecte a la red y listarlo automáticamente.
- Los datos adquiridos se formatean en JSON y se envían a la base de datos PostgreSQL y al frontend Streamlit.
- El frontend se despliega en Streamlit Community Cloud.

## Requisitos
- Python 3.8+
- PostgreSQL
- Streamlit
- Docker (para despliegue final)
- Bibliotecas: pyserial, python-modbus, psycopg2, etc.

---

## Checklist de avances

- [ ] Estructura de carpetas y archivos creada
- [ ] Backend detecta Arduino USB
- [ ] Backend detecta Arduino Ethernet
- [ ] Backend detecta otros dispositivos en la red
- [ ] Backend adquiere y formatea datos en JSON
- [ ] Backend envía datos a PostgreSQL
- [ ] Frontend Streamlit visualiza datos en tiempo real
- [ ] Pruebas locales en Windows completadas
- [ ] Dockerfile creado y probado
- [ ] Despliegue en Jetson Nano realizado
- [ ] Frontend desplegado en Streamlit Community Cloud

---

Este README proporciona una visión general, estructura, flujo de datos y proceso de despliegue para tu proyecto IoT con Python, Arduinos, PostgreSQL y Streamlit.

---

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