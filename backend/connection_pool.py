"""
Pool de conexiones PostgreSQL optimizado para Jetson Nano
Maneja conexiones de forma eficiente con límites apropiados para hardware limitado
"""

import os
import time
import threading
import json
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from psycopg2 import pool
import psycopg2.extras
import psycopg2.errors
from backend.config import get_logger

logger = get_logger(__name__)

class PostgreSQLConnectionPool:
    """Pool de conexiones PostgreSQL optimizado para Jetson Nano"""
    
    def __init__(self):
        # Configuración optimizada para Jetson Nano (RAM limitada)
        self.min_connections = 2       # Mínimo 2 conexiones siempre disponibles
        self.max_connections = 6       # Reducido de 8 a 6 para conservar memoria
        self.connection_timeout = 20   # Aumentado de 15s a 20s
        self.query_timeout = 60        # Aumentado de 30s a 60s para queries complejas
        
        # Pool de conexiones
        self.pool = None
        self.pool_lock = threading.Lock()
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'pool_hits': 0,
            'pool_misses': 0,
            'connection_errors': 0,
            'last_error': None
        }
        
        # Inicializar pool
        self._initialize_pool()
    
    def _initialize_pool(self) -> bool:
        """Inicializar el pool de conexiones con configuración optimizada"""
        try:
            logger.info(f"🔗 Inicializando pool PostgreSQL ({self.min_connections}-{self.max_connections} conexiones)")
            
            # Configuración de conexión
            connection_params = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': os.getenv('DB_PORT', '5432'),
                'database': os.getenv('DB_NAME', 'iot_db'),
                'user': os.getenv('DB_USER', 'iot_user'),
                'password': os.getenv('DB_PASSWORD', 'DAms15820'),
                'connect_timeout': self.connection_timeout,
                # Optimizaciones para Jetson Nano - timeouts más generosos
                'options': '-c statement_timeout=60000 -c idle_in_transaction_session_timeout=120000'
            }
            
            # Crear pool threadsafe
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                **connection_params
            )
            
            logger.info("✅ Pool de conexiones PostgreSQL inicializado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando pool de conexiones: {e}")
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = str(e)
            return False
    
    @contextmanager
    def get_connection(self):
        """Context manager para obtener conexión del pool de forma segura"""
        conn = None
        try:
            with self.pool_lock:
                if not self.pool:
                    self._initialize_pool()
                
                if self.pool:
                    conn = self.pool.getconn()
                    if conn:
                        self.stats['pool_hits'] += 1
                        self.stats['active_connections'] += 1
                        logger.debug(f"🔗 Conexión obtenida del pool (activas: {self.stats['active_connections']})")
                    else:
                        self.stats['pool_misses'] += 1
                        logger.warning("⚠️  No se pudo obtener conexión del pool")
            
            if conn:
                # Configurar conexión para esta sesión
                conn.autocommit = True
                yield conn
            else:
                raise Exception("No se pudo obtener conexión del pool")
                
        except Exception as e:
            logger.error(f"❌ Error usando conexión del pool: {e}")
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = str(e)
            raise
        finally:
            # Devolver conexión al pool
            if conn and self.pool:
                try:
                    with self.pool_lock:
                        self.pool.putconn(conn)
                        self.stats['active_connections'] = max(0, self.stats['active_connections'] - 1)
                        logger.debug(f"🔄 Conexión devuelta al pool (activas: {self.stats['active_connections']})")
                except Exception as e:
                    logger.error(f"❌ Error devolviendo conexión al pool: {e}")
    
    def _serialize_params(self, params: tuple) -> tuple:
        """Serializar parámetros para PostgreSQL, convirtiendo dicts a JSON"""
        if not params:
            return params
        
        serialized = []
        for param in params:
            if isinstance(param, dict):
                # Convertir diccionarios a JSON string
                serialized.append(json.dumps(param))
            elif param is None:
                serialized.append(None)
            else:
                serialized.append(param)
        
        return tuple(serialized)
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[List[Dict[str, Any]]]:
        """Ejecutar consulta usando el pool de conexiones con timeouts inteligentes"""
        
        # Serializar parámetros para evitar errores de tipo
        if params:
            params = self._serialize_params(params)
        
        # Determinar timeout basado en el tipo de query
        query_lower = query.lower().strip()
        is_heavy_query = any(keyword in query_lower for keyword in [
            'sensor_data', 'interval', 'group by', 'order by', 'join'
        ])
        
        # Timeout más generoso para queries pesadas
        timeout_ms = (self.query_timeout * 2 * 1000) if is_heavy_query else (self.query_timeout * 1000)
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # Configurar timeout dinámico para la consulta
                    cursor.execute(f"SET statement_timeout = {timeout_ms}")
                    
                    # Log para queries pesadas
                    if is_heavy_query:
                        logger.debug(f"🐌 Ejecutando query pesada (timeout: {timeout_ms/1000}s): {query[:100]}...")
                    
                    start_time = time.time()
                    
                    # Ejecutar consulta
                    cursor.execute(query, params)
                    
                    execution_time = time.time() - start_time
                    
                    # Log si la query tomó mucho tiempo
                    if execution_time > 5:
                        logger.warning(f"⏱️ Query lenta ({execution_time:.2f}s): {query[:100]}...")
                    
                    if fetch and cursor.description:
                        results = cursor.fetchall()
                        return [dict(row) for row in results]
                    elif cursor.description:
                        return []
                    else:
                        # INSERT, UPDATE, DELETE
                        return [{"affected_rows": cursor.rowcount}]
                        
        except psycopg2.errors.QueryCanceled as e:
            logger.error(f"⏰ Query cancelada por timeout ({timeout_ms/1000}s): {query[:100]}...")
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = f"Query timeout: {str(e)}"
            return None
        except Exception as e:
            logger.error(f"❌ Error ejecutando consulta: {e}")
            logger.error(f"📝 Query: {query[:200]}...")
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = str(e)
            return None
    
    def execute_many(self, query: str, params_list: List[tuple]) -> bool:
        """Ejecutar múltiples consultas en lote (más eficiente)"""
        try:
            # Serializar todos los parámetros
            serialized_params = [self._serialize_params(params) for params in params_list]
            
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.executemany(query, serialized_params)
                    logger.debug(f"📦 Ejecutadas {len(params_list)} consultas en lote")
                    return True
        except Exception as e:
            logger.error(f"❌ Error ejecutando lote de consultas: {e}")
            self.stats['connection_errors'] += 1
            self.stats['last_error'] = str(e)
            return False
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del pool para monitoreo"""
        pool_info = {}
        if self.pool:
            # Información del pool (thread-safe)
            with self.pool_lock:
                try:
                    pool_info = {
                        'min_connections': self.min_connections,
                        'max_connections': self.max_connections,
                        'current_size': len(self.pool._pool) + len(self.pool._used),
                        'available_connections': len(self.pool._pool),
                        'used_connections': len(self.pool._used)
                    }
                except:
                    pool_info = {'error': 'No se puede obtener info del pool'}
        
        return {
            **self.stats,
            'pool_info': pool_info,
            'timestamp': time.time()
        }
    
    def health_check(self) -> bool:
        """Verificar salud del pool de conexiones"""
        try:
            result = self.execute_query("SELECT 1 as test", fetch=True)
            return result is not None and len(result) > 0 and result[0].get('test') == 1
        except:
            return False
    
    def close_all_connections(self):
        """Cerrar todas las conexiones del pool (para shutdown limpio)"""
        if self.pool:
            try:
                with self.pool_lock:
                    self.pool.closeall()
                    logger.info("🔒 Pool de conexiones cerrado")
            except Exception as e:
                logger.error(f"❌ Error cerrando pool: {e}")


# Instancia global del pool (singleton para todo el sistema)
_connection_pool_instance = None
_pool_lock = threading.Lock()

def get_connection_pool() -> PostgreSQLConnectionPool:
    """Factory para obtener instancia singleton del pool de conexiones"""
    global _connection_pool_instance
    
    if _connection_pool_instance is None:
        with _pool_lock:
            if _connection_pool_instance is None:
                _connection_pool_instance = PostgreSQLConnectionPool()
    
    return _connection_pool_instance

def close_connection_pool():
    """Cerrar el pool global (para shutdown de aplicación)"""
    global _connection_pool_instance
    
    if _connection_pool_instance:
        _connection_pool_instance.close_all_connections()
        _connection_pool_instance = None