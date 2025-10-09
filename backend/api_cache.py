"""
Sistema de cache interno para API FastAPI optimizado para Jetson Nano
Proporciona cache en memoria + fallback a disco para garantizar respuestas consistentes
"""

import json
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from backend.config import get_logger

logger = get_logger(__name__)

class APIInternalCache:
    """Cache interno en la API para servir datos incluso cuando PostgreSQL falla"""
    
    def __init__(self, fallback_file: str = "/tmp/iot_api_fallback.json"):
        self.cache = {}  # Cache en memoria: {key: (data, timestamp)}
        self.cache_ttl = 300  # 5 minutos TTL por defecto
        self.fallback_data = {}  # Datos de emergencia
        self.fallback_file = fallback_file
        self.lock = threading.Lock()  # Thread safety
        
        # Cargar datos de fallback del disco si existen
        self._load_fallback_from_disk()
        
        # Iniciar limpieza periódica de cache
        self._start_cache_cleanup()
        
        logger.info(f"✅ APIInternalCache inicializado (fallback: {fallback_file})")
    
    def get_cached_data(self, key: str, ttl_override: int = None) -> Optional[Dict]:
        """Obtiene datos del cache si están frescos"""
        with self.lock:
            if key in self.cache:
                data, timestamp = self.cache[key]
                ttl = ttl_override or self.cache_ttl
                if datetime.now() - timestamp < timedelta(seconds=ttl):
                    logger.debug(f"🎯 Cache HIT para {key}")
                    return data
                else:
                    logger.debug(f"⏰ Cache EXPIRED para {key}")
                    # Remover entrada expirada
                    del self.cache[key]
        
        logger.debug(f"❌ Cache MISS para {key}")
        return None
    
    def set_cache_data(self, key: str, data: Dict, persist_fallback: bool = True):
        """Guarda datos en cache con timestamp"""
        with self.lock:
            self.cache[key] = (data, datetime.now())
            
            # También guardar como fallback persistente para emergencias
            if persist_fallback:
                self.fallback_data[key] = {
                    'data': data,
                    'cached_at': datetime.now().isoformat(),
                    'source': 'cache_update'
                }
                self._persist_fallback()
        
        logger.debug(f"💾 Datos cached para {key}")
    
    def get_fallback_data(self, key: str) -> Optional[Dict]:
        """Obtiene datos de emergencia cuando todo falla"""
        with self.lock:
            fallback_entry = self.fallback_data.get(key)
            if fallback_entry:
                logger.warning(f"🚨 Usando datos de FALLBACK para {key}")
                return fallback_entry.get('data')
        
        logger.error(f"💥 No hay datos de fallback para {key}")
        return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache para monitoreo"""
        with self.lock:
            now = datetime.now()
            fresh_entries = 0
            expired_entries = 0
            
            for key, (data, timestamp) in self.cache.items():
                if now - timestamp < timedelta(seconds=self.cache_ttl):
                    fresh_entries += 1
                else:
                    expired_entries += 1
            
            return {
                'cache_entries_fresh': fresh_entries,
                'cache_entries_expired': expired_entries,
                'cache_entries_total': len(self.cache),
                'fallback_entries': len(self.fallback_data),
                'fallback_file_exists': os.path.exists(self.fallback_file),
                'cache_ttl_seconds': self.cache_ttl,
                'last_updated': datetime.now().isoformat()
            }
    
    def clear_cache(self):
        """Limpia cache en memoria (mantiene fallback)"""
        with self.lock:
            cache_size = len(self.cache)
            self.cache.clear()
            logger.info(f"🧹 Cache limpiado ({cache_size} entradas removidas)")
    
    def _load_fallback_from_disk(self):
        """Carga datos de fallback desde disco al inicializar"""
        try:
            if os.path.exists(self.fallback_file):
                with open(self.fallback_file, 'r') as f:
                    self.fallback_data = json.load(f)
                logger.info(f"📂 Fallback data cargada desde disco ({len(self.fallback_data)} entradas)")
            else:
                logger.info("📂 No existe archivo de fallback, iniciando vacío")
        except Exception as e:
            logger.error(f"❌ Error cargando fallback desde disco: {e}")
            self.fallback_data = {}
    
    def _persist_fallback(self):
        """Guarda datos de emergencia en disco (Jetson Nano)"""
        try:
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.fallback_file), exist_ok=True)
            
            # Guardar con metadata adicional
            fallback_metadata = {
                'generated_at': datetime.now().isoformat(),
                'cache_ttl': self.cache_ttl,
                'total_entries': len(self.fallback_data),
                'data': self.fallback_data
            }
            
            # Escribir atomicamente (rename)
            temp_file = f"{self.fallback_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(fallback_metadata, f, default=str, indent=2)
            os.rename(temp_file, self.fallback_file)
            
            logger.debug(f"💾 Fallback persistido en {self.fallback_file}")
        except Exception as e:
            logger.error(f"❌ Error persistiendo fallback: {e}")
    
    def _start_cache_cleanup(self):
        """Inicia limpieza periódica de cache expirado"""
        def cleanup_loop():
            while True:
                try:
                    time.sleep(60)  # Limpiar cada minuto
                    self._cleanup_expired_entries()
                except Exception as e:
                    logger.error(f"Error en cleanup de cache: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logger.info("🧹 Cache cleanup thread iniciado")
    
    def _cleanup_expired_entries(self):
        """Limpia entradas expiradas del cache"""
        with self.lock:
            now = datetime.now()
            expired_keys = []
            
            for key, (data, timestamp) in self.cache.items():
                if now - timestamp >= timedelta(seconds=self.cache_ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.debug(f"🧹 Cache cleanup: {len(expired_keys)} entradas expiradas removidas")


class CacheKeys:
    """Constantes para keys de cache estandarizados"""
    
    @staticmethod
    def device_data(device_id: str, limit: int = 100, hours: float = None, days: int = None) -> str:
        """Cache key para datos de dispositivo específico"""
        if hours is not None:
            return f"device_data_{device_id}_hours_{hours}"
        elif days is not None:
            return f"device_data_{device_id}_days_{days}"
        else:
            return f"device_data_{device_id}_limit_{limit}"
    
    @staticmethod
    def all_data(hours: float = None, days: int = None, limit: int = None) -> str:
        if hours is not None:
            return f"all_data_hours_{hours}"
        elif days is not None:
            return f"all_data_days_{days}"
        else:
            return f"all_data_limit_{limit or 'default'}"
    
    @staticmethod
    def devices_list(only_online: bool = False) -> str:
        return f"devices_list_online_{only_online}"
    
    @staticmethod
    def device_details(device_id: str) -> str:
        return f"device_details_{device_id}"


# Instancia global del cache (singleton para Jetson Nano)
_cache_instance = None

def get_api_cache() -> APIInternalCache:
    """Factory para obtener instancia singleton del cache"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = APIInternalCache()
    return _cache_instance