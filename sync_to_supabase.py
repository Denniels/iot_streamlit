import json

def get_unsynced_devices():
    query = "SELECT * FROM devices;"
    return db_client.execute_query(query)

def sync_devices_to_supabase():
    devices = get_unsynced_devices()
    if not devices:
        print("No hay dispositivos para sincronizar.")
        return
    # Filtrar y serializar campos válidos
    valid_fields = ['device_id', 'device_type', 'name', 'ip_address', 'port', 'status', 'last_seen', 'metadata', 'updated_at']
    filtered_devices = []
    for device in devices:
        filtered = {k: v for k, v in device.items() if k in valid_fields}
        # Serializar datetime
        for dt_field in ['last_seen', 'updated_at']:
            if dt_field in filtered and hasattr(filtered[dt_field], 'isoformat'):
                filtered[dt_field] = filtered[dt_field].isoformat()
        # Serializar metadata JSON
        if 'metadata' in filtered and isinstance(filtered['metadata'], dict):
            filtered['metadata'] = json.dumps(filtered['metadata'])
        filtered_devices.append(filtered)
    response = supabase.table('devices').upsert(filtered_devices).execute()
    if hasattr(response, 'status') and response.status in [200, 201]:
        print(f"Sincronizados {len(filtered_devices)} dispositivos.")
    else:
        print("Error al sincronizar dispositivos:", response)

"""
Script de sincronización: PostgreSQL local → Supabase
Sincroniza datos nuevos de la tabla sensor_data a Supabase.
"""

import time
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env.local
load_dotenv(dotenv_path=".env.local")
from supabase import create_client, Client
from backend.postgres_client import db_client

# Configuración Supabase desde .env.local
def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url:
        raise Exception("SUPABASE_URL no está definido. Verifica .env.local o variables de entorno.")
    if not key:
        raise Exception("SUPABASE_ANON_KEY no está definido. Verifica .env.local o variables de entorno.")
    return create_client(url, key)

supabase: Client = get_supabase_client()

SYNC_INTERVAL = 60  # segundos
BATCH_SIZE = 100

def get_unsynced_sensor_data():
    # Selecciona los datos no sincronizados
    query = "SELECT * FROM sensor_data WHERE synced IS FALSE LIMIT %s;" % BATCH_SIZE
    return db_client.execute_query(query)

def mark_as_synced(ids):
    if ids:
        id_list = ','.join(str(i) for i in ids)
        query = f"UPDATE sensor_data SET synced = TRUE WHERE id IN ({id_list});"
        db_client.execute_query(query)

def sync_to_supabase():
    while True:
        rows = get_unsynced_sensor_data()
        if not rows:
            print("No hay datos nuevos para sincronizar.")
            time.sleep(SYNC_INTERVAL)
            continue
        # Filtrar solo los campos válidos para Supabase (sin 'synced')
        valid_fields = ['device_id', 'sensor_type', 'value', 'unit', 'timestamp', 'raw_data']
        filtered_rows = []
        ids_to_mark = []
        for row in rows:
            clean_row = {k: v for k, v in row.items() if k not in ['id', 'synced']}
            filtered_row = {k: v for k, v in clean_row.items() if k in valid_fields}
            # Serializar datetime
            if 'timestamp' in filtered_row and hasattr(filtered_row['timestamp'], 'isoformat'):
                filtered_row['timestamp'] = filtered_row['timestamp'].isoformat()
            # Serializar raw_data JSON
            if 'raw_data' in filtered_row and isinstance(filtered_row['raw_data'], dict):
                filtered_row['raw_data'] = json.dumps(filtered_row['raw_data'])
            filtered_rows.append(filtered_row)
            ids_to_mark.append(row['id'])
        print("Datos enviados a Supabase:", filtered_rows)

        # Usar upsert para evitar errores de duplicidad
        try:
            response = supabase.table('sensor_data').upsert(filtered_rows).execute()
            print("Status:", getattr(response, 'status', None))
            print("Response:", getattr(response, 'data', None), getattr(response, 'error', None))
            # Si no hay error, considerar exitosa la sincronización
            if getattr(response, 'error', None) is None:
                print(f"Sincronizados {len(filtered_rows)} registros.")
                mark_as_synced(ids_to_mark)
            else:
                print("Error al sincronizar:", response.error)
        except Exception as e:
            print("Excepción al sincronizar:", e)
        time.sleep(SYNC_INTERVAL)

def test_supabase_connection():
    try:
        response = supabase.table('sensor_data').select('*').limit(1).execute()
        if hasattr(response, 'status') and response.status == 200:
            print("Conexión a Supabase exitosa. Ejemplo de datos:", response.data)
        else:
            print("Conexión a Supabase fallida. Código:", getattr(response, 'status', 'desconocido'), "Respuesta:", response)
    except Exception as e:
        print("Error al conectar a Supabase:", e)

if __name__ == "__main__":
    # test_supabase_connection()
    sync_devices_to_supabase()
    sync_to_supabase()
