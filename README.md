# IoT Streamlit App

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
│   └── db_writer.py               # Envío de datos a PostgreSQL
├── frontend/
│   └── app.py                     # Frontend Streamlit
├── database/
│   └── schema.sql                 # Esquema de la base de datos PostgreSQL
├── requirements.txt               # Dependencias del proyecto
├── README.md                      # Este archivo
└── main.py                        # Orquestador principal
```

## Pipeline de datos

```mermaid
graph TD
    subgraph Dispositivos
        A1[Arduino USB] -- Serial/USB --> B1[Python: arduino_detector.py]
        A2[Arduino Red] -- TCP/UDP --> B2[Python: device_scanner.py]
        A3[Dispositivos Modbus] -- Modbus TCP/RTU --> B3[Python: modbus_scanner.py]
    end
    B1 & B2 & B3 --> C[data_acquisition.py]
    C --> D[db_writer.py]
    D --> E[(PostgreSQL)]
    C --> F[app.py (Streamlit)]
    F --> G[Streamlit Community Cloud]
```

## Flujo de datos
1. **Adquisición**: Los scripts Python detectan y leen datos de Arduinos (USB y red) y dispositivos Modbus.
2. **Formateo**: Los datos se convierten a JSON.
3. **Almacenamiento**: Los datos JSON se insertan en la base de datos PostgreSQL.
4. **Visualización**: El frontend en Streamlit consulta la base de datos y muestra los datos en tiempo real.

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

---

Ahora tu backend y frontend podrán interactuar con la base de datos PostgreSQL alojada en Supabase.
