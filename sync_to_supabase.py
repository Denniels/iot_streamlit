#!/usr/bin/env python3
"""
Sincroniza los datos de la base local PostgreSQL con Supabase
"""
import sys
import time
from datetime import datetime
from backend.postgres_client import PostgreSQLClient
from backend.db_writer import SupabaseClient
from backend.config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def get_latest_supabase_timestamp(supabase_client):
    """Obtiene el timestamp más reciente en Supabase"""
    data = supabase_client.get_latest_sensor_data(limit=1)
    if data:
        return data[0]['timestamp']
    return None

def fetch_new_local_data(pg_client, last_timestamp):
    """Obtiene los datos locales más nuevos que no están en Supabase"""
    if last_timestamp:
        query = """
            SELECT * FROM sensor_data WHERE timestamp > %s ORDER BY timestamp ASC
        """
        params = (last_timestamp,)
    else:
        query = "SELECT * FROM sensor_data ORDER BY timestamp ASC"
        params = None
    return pg_client.execute_query(query, params)

def sync_data():
    logger.info("Iniciando sincronización de datos con Supabase...")
    pg_client = PostgreSQLClient()
    supabase_client = SupabaseClient()

    # 1. Obtener el último timestamp en Supabase
    last_supabase_ts = get_latest_supabase_timestamp(supabase_client)
    logger.info(f"Último timestamp en Supabase: {last_supabase_ts}")

    # 2. Obtener datos nuevos de la base local
    new_data = fetch_new_local_data(pg_client, last_supabase_ts)
    logger.info(f"Datos nuevos a sincronizar: {len(new_data) if new_data else 0}")

    # 3. Insertar en Supabase
    success_count = 0
    for row in new_data or []:
        # Eliminar el campo 'id' para evitar conflictos
        row.pop('id', None)
        # Convertir el campo 'value' a float si es posible
        if 'value' in row:
            try:
                from decimal import Decimal
                if isinstance(row['value'], Decimal):
                    row['value'] = float(row['value'])
                elif isinstance(row['value'], str):
                    row['value'] = float(row['value'])
            except Exception:
                pass
        # Convertir timestamp y created_at a string ISO si son datetime
        for k in ['timestamp', 'created_at']:
            if k in row:
                try:
                    if hasattr(row[k], 'isoformat'):
                        row[k] = row[k].isoformat()
                except Exception:
                    pass
        try:
            if supabase_client.insert_sensor_data(row):
                success_count += 1
        except Exception as e:
            logger.error(f"Error sincronizando fila: {e}")

    logger.info(f"Sincronización completa. Filas sincronizadas: {success_count}")
    print(f"Sincronización completa. Filas sincronizadas: {success_count}")
    return success_count

def main():
    try:
        logger.info("Servicio de sincronización Supabase iniciado.")
        while True:
            sync_data()
            time.sleep(60)  # Sincroniza cada minuto
    except KeyboardInterrupt:
        logger.info("Sincronización detenida por el usuario.")
        print("Sincronización detenida por el usuario.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error en la sincronización: {e}")
        print(f"Error en la sincronización: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
