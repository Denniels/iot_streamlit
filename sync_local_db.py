#!/usr/bin/env python3
"""
Sincroniza los datos de la base local PostgreSQL con la propia base local (modo local, sin Supabase)
"""
import sys
import time
from datetime import datetime
from backend.postgres_client import PostgreSQLClient
from backend.db_writer import LocalPostgresClient
from backend.config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def get_latest_local_timestamp(local_client):
    """Obtiene el timestamp más reciente en la base local"""
    data = local_client.get_latest_sensor_data(limit=1)
    if data:
        return data[0]['timestamp']
    return None

def fetch_new_local_data(pg_client, last_timestamp):
    """Obtiene los datos locales más nuevos que no están marcados como sincronizados"""
    if last_timestamp:
        query = """
            SELECT * FROM sensor_data WHERE timestamp > %s AND (synced IS NULL OR synced = FALSE) ORDER BY timestamp ASC
        """
        params = (last_timestamp,)
    else:
        query = "SELECT * FROM sensor_data WHERE (synced IS NULL OR synced = FALSE) ORDER BY timestamp ASC"
        params = None
    return pg_client.execute_query(query, params)

def sync_data():
    logger.info("Iniciando sincronización de datos con la base local...")
    pg_client = PostgreSQLClient()
    local_client = LocalPostgresClient()

    # 1. Obtener el último timestamp en la base local
    last_local_ts = get_latest_local_timestamp(local_client)
    logger.info(f"Último timestamp en base local: {last_local_ts}")

    # 2. Obtener datos nuevos de la base local
    new_data = fetch_new_local_data(pg_client, last_local_ts)
    logger.info(f"Datos nuevos a sincronizar: {len(new_data) if new_data else 0}")

    # 3. Insertar en la base local (simulado, solo marca como sincronizado)
    success_count = 0
    for row in new_data or []:
        row.pop('id', None)
        row.pop('created_at', None)
        if 'value' in row:
            try:
                from decimal import Decimal
                if isinstance(row['value'], Decimal):
                    row['value'] = float(row['value'])
                elif isinstance(row['value'], str):
                    row['value'] = float(row['value'])
            except Exception:
                pass
        if 'timestamp' in row:
            try:
                if hasattr(row['timestamp'], 'isoformat'):
                    row['timestamp'] = row['timestamp'].isoformat()
            except Exception:
                pass
        try:
            if local_client.insert_sensor_data(row):
                success_count += 1
                update_query = "UPDATE sensor_data SET synced = TRUE WHERE device_id = %s AND sensor_type = %s AND timestamp = %s"
                update_params = (row['device_id'], row['sensor_type'], row['timestamp'])
                pg_client.execute_query(update_query, update_params)
        except Exception as e:
            logger.error(f"Error sincronizando fila: {e}")
    logger.info(f"Sincronización completa. Filas sincronizadas: {success_count}")
    print(f"Sincronización completa. Filas sincronizadas: {success_count}")
    return success_count

def main():
    try:
        logger.info("Servicio de sincronización local iniciado.")
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
