"""
Cliente para interactuar con Supabase
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from backend.config import Config, get_logger

logger = get_logger(__name__)

class SupabaseClient:
    """Cliente para operaciones con Supabase"""
    
    def __init__(self):
        try:
            self.client: Client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_SERVICE_KEY or Config.SUPABASE_KEY
            )
            logger.info("Conexión a Supabase establecida")
        except Exception as e:
            logger.error(f"Error conectando a Supabase: {e}")
            self.client = None
    
    def register_device(self, device_data: Dict[str, Any]) -> bool:
        """Registrar o actualizar un dispositivo"""
        if not self.client:
            return False
        
        try:
            # Intentar insertar, si existe actualizarlo
            result = self.client.table('devices').upsert(
                device_data,
                on_conflict='device_id'
            ).execute()
            
            logger.info(f"Dispositivo registrado: {device_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error registrando dispositivo: {e}")
            return False
    
    def insert_sensor_data(self, sensor_data: Dict[str, Any]) -> bool:
        """Insertar datos de sensor"""
        if not self.client:
            return False
        
        try:
            result = self.client.table('sensor_data').insert(sensor_data).execute()
            logger.debug(f"Datos insertados para dispositivo: {sensor_data.get('device_id')}")
            return True
        except Exception as e:
            logger.error(f"Error insertando datos de sensor: {e}")
            return False
    
    def update_device_status(self, device_id: str, status: str) -> bool:
        """Actualizar estado de dispositivo"""
        if not self.client:
            return False
        
        try:
            result = self.client.table('devices').update({
                'status': status,
                'last_seen': datetime.now().isoformat()
            }).eq('device_id', device_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error actualizando estado del dispositivo {device_id}: {e}")
            return False
    
    def log_system_event(self, event_type: str, device_id: Optional[str] = None, 
                        message: str = "", metadata: Optional[Dict] = None) -> bool:
        """Registrar evento del sistema"""
        if not self.client:
            return False
        
        try:
            event_data = {
                'event_type': event_type,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
            
            if device_id:
                event_data['device_id'] = device_id
            if metadata:
                event_data['metadata'] = metadata
            
            result = self.client.table('system_events').insert(event_data).execute()
            return True
        except Exception as e:
            logger.error(f"Error registrando evento del sistema: {e}")
            return False
    
    def get_devices(self) -> List[Dict]:
        """Obtener todos los dispositivos"""
        if not self.client:
            return []
        
        try:
            result = self.client.table('devices').select('*').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo dispositivos: {e}")
            return []
    
    def get_latest_sensor_data(self, limit: int = 100) -> List[Dict]:
        """Obtener datos más recientes de sensores"""
        if not self.client:
            return []
        
        try:
            result = self.client.table('sensor_data').select('*').order('timestamp', desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error obteniendo datos de sensores: {e}")
            return []
