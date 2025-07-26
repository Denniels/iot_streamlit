import os
import json
from dotenv import load_dotenv
from backend.postgres_client import db_client
from supabase import create_client, Client

# Cargar variables de entorno
load_dotenv('.env.local')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 1. Tomar datos de Postgres y enviarlos a Supabase
BATCH_SIZE = 10

def get_unsynced_sensor_data():
    query = f"SELECT * FROM sensor_data WHERE synced IS FALSE LIMIT {BATCH_SIZE};"
    return db_client.execute_query(query)

def mark_as_synced(ids):
    if ids:
        id_list = ','.join(str(i) for i in ids)
        query = f"UPDATE sensor_data SET synced = TRUE WHERE id IN ({id_list});"
        db_client.execute_query(query)

def sync_to_supabase():
    total_synced = 0
    while True:
        rows = get_unsynced_sensor_data()
        if not rows:
            break
        valid_fields = ['device_id', 'sensor_type', 'value', 'unit', 'timestamp', 'raw_data']
        filtered_rows = []
        ids_to_mark = []
        for row in rows:
            clean_row = {k: v for k, v in row.items() if k not in ['id', 'synced']}
            filtered_row = {k: v for k, v in clean_row.items() if k in valid_fields}
            if 'timestamp' in filtered_row and hasattr(filtered_row['timestamp'], 'isoformat'):
                filtered_row['timestamp'] = filtered_row['timestamp'].isoformat()
            if 'raw_data' in filtered_row and isinstance(filtered_row['raw_data'], dict):
                filtered_row['raw_data'] = json.dumps(filtered_row['raw_data'])
            filtered_rows.append(filtered_row)
            ids_to_mark.append(row['id'])
        response = supabase.table('sensor_data').upsert(filtered_rows).execute()
        if getattr(response, 'error', None) is None:
            print(f"Sincronizados {len(filtered_rows)} registros.")
            mark_as_synced(ids_to_mark)
            total_synced += len(filtered_rows)
        else:
            print("Error al sincronizar:", response.error)
            break
    if total_synced > 0:
        print(f"Sincronización completa: {total_synced} registros enviados.")
        return True
    else:
        print("No hay datos nuevos para sincronizar.")
        return False

# 2. Consultar Supabase para verificar los datos

def check_supabase_data():
    response = supabase.table('sensor_data').select('*').limit(BATCH_SIZE).execute()
    if getattr(response, 'error', None) is None:
        print("Datos en Supabase:")
        print(json.dumps(response.data, indent=2, ensure_ascii=False))
        return True
    else:
        print("Error consultando Supabase:", response.error)
        return False

if __name__ == "__main__":
    print("--- Sincronizando datos de Postgres a Supabase ---")
    ok = sync_to_supabase()
    if ok:
        print("--- Verificando datos en Supabase ---")
        check_supabase_data()
    else:
        print("No se pudo sincronizar.")
