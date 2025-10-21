# Sincronización de Base de Datos IoT Jetson Nano a AWS PostgreSQL

## 1. Crear una base de datos PostgreSQL en AWS (RDS)

### Paso a paso (sin CLI, solo consola web):

1. Accede a la consola de AWS: https://console.aws.amazon.com/
2. Ve a **RDS** (Relational Database Service).
3. Haz clic en "Create database".
4. Selecciona **Standard Create** y el motor **PostgreSQL**.
5. Elige la versión recomendada (ej. PostgreSQL 14.x).
6. Configura:
   - **DB instance identifier**: iot_streamlit
   - **Master username**: iot_user
   - **Master password**: (elige una segura)
   - **Instance type**: db.t3.micro (para pruebas)
   - **Storage**: 20GB (ajusta según necesidad)
7. En **Connectivity**:
   - Selecciona la VPC adecuada.
   - Habilita "Public access" si quieres conectar desde fuera de AWS (solo para pruebas, luego restringe por seguridad).
   - Agrega tu IP pública en el grupo de seguridad para permitir conexiones al puerto 5432.
8. Finaliza la creación y espera a que el estado sea "Available".
9. Apunta el **endpoint** y el **puerto** (ejemplo: iot-streamlit.xxxxxxx.us-east-1.rds.amazonaws.com:5432).

10. En la consola de RDS, ve a la instancia, haz clic en "Query Editor" y crea las tablas copiando el contenido de `database/schema.sql` de tu proyecto.

## 2. Script Python para sincronizar datos locales a AWS

Este script lee los datos de la base local cada minuto, los agrupa por dispositivo y los envía a la base AWS.

### Requisitos
- Instala las dependencias:
  ```bash
  pip install psycopg2-binary
  ```
- Crea un archivo `.env` con las credenciales de ambas bases:
  ```ini
  # Local
  LOCAL_DB_HOST=localhost
  LOCAL_DB_PORT=5432
  LOCAL_DB_NAME=iot_db
  LOCAL_DB_USER=iot_user
  LOCAL_DB_PASSWORD=tu_password_local

  # AWS
  AWS_DB_HOST=iot-streamlit.xxxxxxx.us-east-1.rds.amazonaws.com
  AWS_DB_PORT=5432
  AWS_DB_NAME=iot_db
  AWS_DB_USER=iot_user
  AWS_DB_PASSWORD=tu_password_aws
  ```

### sync_to_aws.py
```python
import os
import time
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = {
    'host': os.getenv('LOCAL_DB_HOST'),
    'port': os.getenv('LOCAL_DB_PORT'),
    'dbname': os.getenv('LOCAL_DB_NAME'),
    'user': os.getenv('LOCAL_DB_USER'),
    'password': os.getenv('LOCAL_DB_PASSWORD'),
}
AWS_DB = {
    'host': os.getenv('AWS_DB_HOST'),
    'port': os.getenv('AWS_DB_PORT'),
    'dbname': os.getenv('AWS_DB_NAME'),
    'user': os.getenv('AWS_DB_USER'),
    'password': os.getenv('AWS_DB_PASSWORD'),
}

SYNC_INTERVAL = 60  # segundos
SYNC_WINDOW = 120   # segundos (sincroniza últimos 2 minutos)

def get_local_data():
    conn = psycopg2.connect(**LOCAL_DB)
    cur = conn.cursor()
    since = datetime.utcnow() - timedelta(seconds=SYNC_WINDOW)
    cur.execute("""
        SELECT device_id, sensor_type, value, unit, raw_data, timestamp
        FROM sensor_data
        WHERE timestamp >= %s
        ORDER BY device_id, timestamp
    """, (since,))
    rows = cur.fetchall()
    conn.close()
    # Agrupar por dispositivo
    data = {}
    for r in rows:
        dev = r[0]
        if dev not in data:
            data[dev] = []
        data[dev].append({
            'sensor_type': r[1],
            'value': r[2],
            'unit': r[3],
            'raw_data': r[4],
            'timestamp': r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5])
        })
    return data

def send_to_aws(data):
    conn = psycopg2.connect(**AWS_DB)
    cur = conn.cursor()
    for device_id, sensors in data.items():
        for s in sensors:
            cur.execute("""
                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (device_id, sensor_type, timestamp) DO NOTHING;
            """, (
                device_id, s['sensor_type'], s['value'], s['unit'], s['raw_data'], s['timestamp']
            ))
    conn.commit()
    conn.close()

def main():
    while True:
        try:
            data = get_local_data()
            if data:
                send_to_aws(data)
            time.sleep(SYNC_INTERVAL)
        except Exception as e:
            print(f"Error en sincronización: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
```

## 3. Crear el servicio systemd

1. Guarda el script como `/home/daniel/repos/iot_streamlit/sync_to_aws.py`.
2. Crea el archivo de servicio `/etc/systemd/system/sync_to_aws.service`:

```
[Unit]
Description=Sincroniza datos IoT Jetson Nano a AWS PostgreSQL
After=network.target

[Service]
Type=simple
User=daniel
WorkingDirectory=/home/daniel/repos/iot_streamlit
ExecStart=/usr/bin/python3 /home/daniel/repos/iot_streamlit/sync_to_aws.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. Recarga systemd y habilita el servicio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sync_to_aws.service
sudo systemctl start sync_to_aws.service
```

## 4. Seguridad y recomendaciones
- Usa VPC y grupos de seguridad en AWS para restringir el acceso solo a la IP de la Jetson Nano.
- Cambia las contraseñas por valores seguros.
- Haz pruebas con una instancia pequeña y monitorea el tráfico y los costos.
- Revisa los logs del servicio en `/var/log/syslog` o con `journalctl -u sync_to_aws.service`.

---

Este flujo permite sincronizar los datos de sensores de tu Jetson Nano a una base de datos PostgreSQL en AWS, sin instalar CLI ni herramientas extra en la Jetson, solo usando Python y systemd.
