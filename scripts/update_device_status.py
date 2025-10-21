#!/usr/bin/env python3
"""
Script para actualizar automáticamente el last_seen de dispositivos
basado en el timestamp del último dato de sensor recibido.
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import Config, get_logger, setup_logging
from backend.pooled_postgres_client import PooledPostgresClient
import time

def update_device_last_seen():
    """Actualizar last_seen de todos los dispositivos basado en sus últimos datos de sensor"""
    setup_logging()
    logger = get_logger(__name__)
    
    try:
        db_client = PooledPostgresClient()
        
        # Query para actualizar last_seen de cada dispositivo con el timestamp del último sensor_data
        update_query = """
            UPDATE devices 
            SET last_seen = subquery.max_timestamp, 
                updated_at = NOW()
            FROM (
                SELECT device_id, MAX(timestamp) as max_timestamp 
                FROM sensor_data 
                GROUP BY device_id
            ) subquery
            WHERE devices.device_id = subquery.device_id
            AND (devices.last_seen IS NULL OR devices.last_seen < subquery.max_timestamp);
        """
        
        result = db_client.execute_query(update_query, use_cache=False)
        if result is not None:
            logger.info("✅ Dispositivos actualizados correctamente")
            return True
        else:
            logger.error("❌ Error actualizando dispositivos")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error en update_device_last_seen: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Actualizando last_seen de dispositivos...")
    if update_device_last_seen():
        print("✅ Actualización completada")
    else:
        print("❌ Error en la actualización")