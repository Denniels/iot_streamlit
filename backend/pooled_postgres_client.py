"""
Cliente PostgreSQL con pool de conexiones para reemplazar LocalPostgresClient
Optimizado para Jetson Nano con manejo eficiente de recursos
"""

import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from backend.config import get_logger
from backend.connection_pool import get_connection_pool

logger = get_logger(__name__)

class PooledPostgresClient:
    """Cliente PostgreSQL que usa pool de conexiones para mejor rendimiento y gestión de recursos"""
    
    def __init__(self):
        self.pool = get_connection_pool()
        self.query_cache = {}  # Cache simple para queries frecuentes
        self.cache_ttl = 30    # 30 segundos de cache
        
    def _get_cache_key(self, query: str, params: tuple = None) -> str:
        """Generar clave de cache para la consulta"""
        return f"{hash(query)}_{hash(str(params)) if params else 'none'}"
    
    def _is_cache_valid(self, cache_entry: dict) -> bool:
        """Verificar si la entrada de cache sigue siendo válida"""
        return time.time() - cache_entry['timestamp'] < self.cache_ttl
    
    def _should_cache_query(self, query: str) -> bool:
        """Determinar si una consulta debe ser cacheada"""
        # Solo cachear consultas SELECT que no cambien datos
        query_lower = query.lower().strip()
        return (query_lower.startswith('select') and 
                'devices' in query_lower and 
                'limit' in query_lower)
    
    def execute_query(self, query: str, params: tuple = None, use_cache: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Ejecutar consulta usando el pool de conexiones con cache opcional"""
        
        # Verificar cache para consultas SELECT frecuentes
        if use_cache and self._should_cache_query(query):
            cache_key = self._get_cache_key(query, params)
            if cache_key in self.query_cache:
                cache_entry = self.query_cache[cache_key]
                if self._is_cache_valid(cache_entry):
                    logger.debug(f"🎯 Cache HIT para query: {query[:50]}...")
                    return cache_entry['result']
        
        # Ejecutar consulta usando el pool
        result = self.pool.execute_query(query, params)
        
        # Guardar en cache si es apropiado
        if result is not None and use_cache and self._should_cache_query(query):
            cache_key = self._get_cache_key(query, params)
            self.query_cache[cache_key] = {
                'result': result,
                'timestamp': time.time()
            }
            logger.debug(f"💾 Resultado cacheado para query: {query[:50]}...")
        
        return result
    
    def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Ejecutar múltiples consultas en lote"""
        return self.pool.execute_many(query, params_list)
    
    # === MÉTODOS COMPATIBLES CON LocalPostgresClient ===
    
    def get_devices(self, only_online: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        """Obtener lista de dispositivos"""
        try:
            if only_online:
                query = """
                    SELECT device_id, device_type, ip_address, port, mac_address, 
                           status, last_seen, updated_at, created_at
                    FROM devices 
                    WHERE status = 'online' 
                    ORDER BY updated_at DESC 
                    LIMIT %s
                """
            else:
                query = """
                    SELECT device_id, device_type, ip_address, port, mac_address, 
                           status, last_seen, updated_at, created_at
                    FROM devices 
                    ORDER BY updated_at DESC 
                    LIMIT %s
                """
            
            result = self.execute_query(query, (limit,))
            return result if result else []
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo dispositivos: {e}")
            return []
    
    def get_device_by_id(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Obtener dispositivo específico por ID"""
        try:
            query = """
                SELECT device_id, device_type, ip_address, port, mac_address, 
                       status, last_seen, updated_at, created_at
                FROM devices 
                WHERE device_id = %s
            """
            result = self.execute_query(query, (device_id,))
            return result[0] if result and len(result) > 0 else None
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo dispositivo {device_id}: {e}")
            return None
    
    def save_device(self, device_data: Dict[str, Any]) -> bool:
        """Guardar o actualizar dispositivo"""
        try:
            query = """
                INSERT INTO devices (device_id, device_type, ip_address, port, mac_address, status, last_seen, updated_at)
                VALUES (%(device_id)s, %(device_type)s, %(ip_address)s, %(port)s, %(mac_address)s, %(status)s, %(last_seen)s, %(updated_at)s)
                ON CONFLICT (device_id) 
                DO UPDATE SET 
                    device_type = EXCLUDED.device_type,
                    ip_address = EXCLUDED.ip_address,
                    port = EXCLUDED.port,
                    mac_address = EXCLUDED.mac_address,
                    status = EXCLUDED.status,
                    last_seen = EXCLUDED.last_seen,
                    updated_at = EXCLUDED.updated_at
            """
            
            # Asegurar formato correcto de timestamp
            if 'updated_at' not in device_data:
                device_data['updated_at'] = datetime.now(timezone.utc)
            if 'last_seen' not in device_data:
                device_data['last_seen'] = datetime.now(timezone.utc)
            
            result = self.execute_query(query, device_data, use_cache=False)
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Error guardando dispositivo: {e}")
            return False
    
    def get_sensor_data(self, device_id: str = None, limit: int = 1000, 
                       hours: float = None, days: int = None) -> List[Dict[str, Any]]:
        """Obtener datos de sensores con filtros opcionales"""
        try:
            # Construir consulta base
            if device_id:
                base_query = """
                    SELECT device_id, sensor_type, value, unit, raw_data, timestamp
                    FROM sensor_data 
                    WHERE device_id = %s
                """
                params = [device_id]
            else:
                base_query = """
                    SELECT device_id, sensor_type, value, unit, raw_data, timestamp
                    FROM sensor_data 
                    WHERE 1=1
                """
                params = []
            
            # Agregar filtros temporales
            if hours is not None:
                base_query += " AND timestamp >= NOW() - INTERVAL '%s hours'"
                params.append(hours)
            elif days is not None:
                base_query += " AND timestamp >= NOW() - INTERVAL '%s days'"
                params.append(days)
            
            # Ordenar y limitar
            base_query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
            
            result = self.execute_query(base_query, tuple(params))
            return result if result else []
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo datos de sensores: {e}")
            return []
    
    def save_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Guardar datos de sensor"""
        try:
            query = """
                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp)
                VALUES (%(device_id)s, %(sensor_type)s, %(value)s, %(unit)s, %(raw_data)s, %(timestamp)s)
            """
            
            # Asegurar formato correcto
            if 'timestamp' not in sensor_data:
                sensor_data['timestamp'] = datetime.now(timezone.utc)
            
            # Convertir raw_data a JSON si es dict
            if isinstance(sensor_data.get('raw_data'), dict):
                sensor_data['raw_data'] = json.dumps(sensor_data['raw_data'])
            
            result = self.execute_query(query, sensor_data, use_cache=False)
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Error guardando datos de sensor: {e}")
            return False
    
    def save_sensor_data_batch(self, sensor_data_list: List[Dict[str, Any]]) -> bool:
        """Guardar múltiples datos de sensores en lote (más eficiente)"""
        try:
            query = """
                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            # Preparar datos para executemany
            params_list = []
            for sensor_data in sensor_data_list:
                if 'timestamp' not in sensor_data:
                    sensor_data['timestamp'] = datetime.now(timezone.utc)
                
                if isinstance(sensor_data.get('raw_data'), dict):
                    sensor_data['raw_data'] = json.dumps(sensor_data['raw_data'])
                
                params_list.append((
                    sensor_data['device_id'],
                    sensor_data['sensor_type'],
                    sensor_data['value'],
                    sensor_data['unit'],
                    sensor_data['raw_data'],
                    sensor_data['timestamp']
                ))
            
            return self.execute_many(query, params_list)
            
        except Exception as e:
            logger.error(f"❌ Error guardando lote de datos de sensores: {e}")
            return False
    
    def log_system_event(self, event_type: str, description: str, device_id: str = None, severity: str = 'info') -> bool:
        """Registrar evento del sistema"""
        try:
            query = """
                INSERT INTO system_events (event_type, description, device_id, severity, timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            params = (
                event_type,
                description,
                device_id,
                severity,
                datetime.now(timezone.utc)
            )
            
            result = self.execute_query(query, params, use_cache=False)
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ Error registrando evento del sistema: {e}")
            return False
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del pool de conexiones"""
        return self.pool.get_pool_stats()
    
    def health_check(self) -> bool:
        """Verificar salud de la conexión"""
        return self.pool.health_check()
    
    def clear_cache(self):
        """Limpiar cache de consultas"""
        self.query_cache.clear()
        logger.info("🧹 Cache de consultas limpiado")


# Factory functions para compatibilidad con código existente
def get_pooled_client() -> PooledPostgresClient:
    """Obtener cliente PostgreSQL con pool de conexiones"""
    return PooledPostgresClient()

# Para migración gradual - alias temporal
LocalPostgresClient = PooledPostgresClient