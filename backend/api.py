"""
API REST con FastAPI para el backend IoT
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional


import uvicorn
from datetime import datetime, timezone, timedelta
import dateutil.parser
import asyncio
import requests
import threading
import time
import toml
import os

# Importar función de estado de servicios
from backend.service_status import get_services_status

from backend.config import Config, get_logger, setup_logging
from backend.data_acquisition import DataAcquisition
from backend.pooled_postgres_client import PooledPostgresClient
from backend.api_cache import get_api_cache, CacheKeys

# Configuración de logging
setup_logging(Config.BACKEND_LOG)
logger = get_logger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="IoT Streamlit Backend",
    description="API REST para detección de dispositivos Arduino y Modbus",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS para permitir conexiones desde Streamlit Community Cloud
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios específicos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Instancia global del sistema de adquisición y cache
data_acquisition = DataAcquisition()
acquisition_task = None
api_cache = get_api_cache()  # Cache interno para resilencia


# --- Cloudflare Tunnel management ---

# Ruta al archivo de configuración del túnel Cloudflare
CF_CREDENTIALS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'secrets_tunnel.toml'))


# --- Endpoint que lee la URL pública de Cloudflare Tunnel en tiempo real ---
@app.get("/cf_url")
async def get_cf_url():
    """Devuelve la URL pública actual del túnel Cloudflare leyendo el archivo secrets_tunnel.toml"""
    try:
        if os.path.exists(CF_CREDENTIALS_PATH):
            data = toml.load(CF_CREDENTIALS_PATH)
            cf_url = data.get('cloudflare', {}).get('url', None)
            if cf_url:
                return {"success": True, "cf_url": cf_url}
            else:
                return {"success": False, "cf_url": None, "error": "No se encontró la URL en el archivo."}
        else:
            return {"success": False, "cf_url": None, "error": "Archivo secrets_tunnel.toml no encontrado."}
    except Exception as e:
        return {"success": False, "cf_url": None, "error": str(e)}


# Modelo para recibir notificaciones de cambio de URL del túnel
class TunnelUrlUpdate(BaseModel):
    tunnel_url: str
    timestamp: Optional[str] = None


@app.post("/internal/tunnel_url_update")
async def tunnel_url_update(update: TunnelUrlUpdate):
    """Endpoint interno para recibir notificaciones de cambio de URL del túnel Cloudflare"""
    try:
        logger.info(f"📡 Notificación de cambio de URL del túnel: {update.tunnel_url}")
        
        # Actualizar caché interno si es necesario
        api_cache.set(CacheKeys.TUNNEL_URL, {
            "url": update.tunnel_url,
            "last_updated": update.timestamp or datetime.now(timezone.utc).isoformat()
        }, ttl=3600 * 24)  # Cache por 24 horas
        
        logger.info(f"✅ URL del túnel actualizada en cache: {update.tunnel_url}")
        
        return {
            "success": True,
            "message": "Tunnel URL actualizada correctamente",
            "url": update.tunnel_url
        }
    except Exception as e:
        logger.error(f"❌ Error actualizando URL del túnel: {e}")
        return {
            "success": False,
            "message": f"Error actualizando URL: {str(e)}"
        }


# Modelos Pydantic para validación de datos
class DeviceStatus(BaseModel):
    device_id: str
    device_type: str
    status: str
    last_seen: Optional[datetime] = None
    error_message: Optional[str] = None

class SystemStatus(BaseModel):
    timestamp: datetime
    running: bool
    devices: Dict[str, int]
    last_data: Optional[str] = None
    errors: List[str] = []

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime

# Eventos de inicio y cierre

@app.on_event("startup")
async def startup_event():
    """Inicializar el sistema al arrancar la API"""
    logger.info("Iniciando API REST IoT Backend...")
    try:
        # Inicializar detectores de dispositivos (comentado para pruebas de integridad)
        # data_acquisition.initialize_devices()
        logger.info("[TEST] Inicialización de dispositivos deshabilitada para prueba de API.")
    except Exception as e:
        logger.error(f"Error en inicialización: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpiar recursos al cerrar la API"""
    logger.info("Cerrando API REST...")
    
    global acquisition_task
    if acquisition_task:
        acquisition_task = None
    
    data_acquisition.stop_acquisition()

# Endpoints principales

# --- Nuevo endpoint: Estado de los servicios systemd ---
@app.get("/service_status")
async def service_status():
    """Devuelve el estado de los servicios systemd relevantes para el dashboard"""
    try:
        status = get_services_status()
        return {"success": True, "services": status}
    except Exception as e:
        logger.error(f"Error obteniendo estado de servicios: {e}")
        return {"success": False, "error": str(e)}
@app.get("/", response_model=ApiResponse)
async def root():
    """Endpoint raíz con información de la API"""
    return ApiResponse(
        success=True,
        message="IoT Streamlit Backend API - Sistema activo",
        data={
            "version": "1.0.0",
            "documentation": "/docs",
            "status": "/status",
            "devices": "/devices",
            "data": "/data"
        },
        timestamp=datetime.now(timezone.utc)
    )

@app.get("/health")
async def health_check():
    """Verificación de salud del sistema con información de cache"""
    try:
        db_client = PooledPostgresClient()
        # Probar conexión a base de datos
        devices = db_client.get_devices()
        
        # Obtener estadísticas del cache
        cache_stats = api_cache.get_cache_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc),
            "database": "connected",
            "devices_count": len(devices),
            "cache": cache_stats
        }
    except Exception as e:
        # Si la BD falla, reportar estado degradado pero mantener info de cache
        cache_stats = api_cache.get_cache_stats()
        return {
            "status": "degraded",
            "timestamp": datetime.now(timezone.utc),
            "database": f"error: {str(e)}",
            "devices_count": 0,
            "cache": cache_stats,
            "fallback_available": cache_stats.get('fallback_entries', 0) > 0
        }

@app.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Obtener estado actual del sistema"""
    try:
        status = data_acquisition.get_current_status()
        
        return SystemStatus(
            timestamp=datetime.fromisoformat(status['timestamp']),
            running=status['running'],
            devices=status['devices'],
            last_data=status.get('last_data'),
            errors=status.get('errors', [])
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo estado del sistema: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )

@app.get("/devices", response_model=ApiResponse)
async def get_devices(only_online: bool = False):
    """Obtener lista de dispositivos con cache resiliente"""
    cache_key = CacheKeys.devices_list(only_online)
    
    # 1. Intentar cache fresco (TTL: 2 minutos para dispositivos)
    cached_result = api_cache.get_cached_data(cache_key, ttl_override=120)
    if cached_result:
        return ApiResponse(
            success=True,
            message=f"Dispositivos con sensores (cache) - online_filter: {only_online}",
            data=cached_result,
            timestamp=datetime.now()
        )
    
    # 2. Intentar base de datos
    try:
        db_client = PooledPostgresClient()
        devices = db_client.get_devices()
        
        # Filtrar solo dispositivos que tienen datos de sensores
        sensor_device_types = ['arduino_ethernet', 'esp32_wifi', 'arduino_usb', 'modbus_device']

        # Formatear información de dispositivos con sensores
        formatted_devices = []
        for device in devices:
            device_type = device.get('device_type')
            device_id = device.get('device_id')
            
            # Solo incluir dispositivos que pueden tener sensores
            if device_type in sensor_device_types:
                # Verificar que el dispositivo tiene datos recientes
                recent_data = db_client.get_sensor_data(device_id=device_id, limit=1)
                
                # Normalizar y formatear campos para la respuesta JSON
                ip_raw = device.get('ip_address')
                try:
                    ip_addr = str(ip_raw) if ip_raw is not None else None
                except Exception:
                    ip_addr = None

                # Preparar estructura básica
                dev = {
                    'device_id': device_id,
                    'device_type': device_type,
                    'ip_address': ip_addr,
                    'port': device.get('port'),
                    'status': device.get('status'),
                    'description': device.get('description'),
                    'has_data': len(recent_data) > 0,
                    'last_seen': None,
                    'online': False
                }

                # Determinar si el dispositivo está 'online' según last_seen (configurable)
                try:
                    last_seen_raw = device.get('last_seen')
                    last_dt = None
                    if last_seen_raw:
                        if isinstance(last_seen_raw, str):
                            try:
                                last_dt = dateutil.parser.isoparse(last_seen_raw)
                            except Exception:
                                last_dt = None
                        elif isinstance(last_seen_raw, datetime):
                            last_dt = last_seen_raw

                    if last_dt:
                        # Asegurar tz-aware
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        now = datetime.now(timezone.utc)
                        dev['online'] = (now - last_dt) <= timedelta(minutes=5)
                        dev['last_seen'] = last_dt.isoformat()
                    else:
                        # Si no se pudo parsear, devolver el raw tal cual
                        dev['last_seen'] = str(last_seen_raw) if last_seen_raw is not None else None
                except Exception:
                    dev['online'] = False
                    dev['last_seen'] = str(device.get('last_seen')) if device.get('last_seen') is not None else None

                formatted_devices.append(dev)
        
        # Si se solicitó filtrar solo online, aplicar filtro
        if only_online:
            filtered = [d for d in formatted_devices if d.get('online')]
        else:
            filtered = formatted_devices

        # Guardar en cache para futuras consultas
        api_cache.set_cache_data(cache_key, filtered)

        return ApiResponse(
            success=True,
            message=f"{len(filtered)} dispositivos con sensores encontrados",
            data=filtered,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo dispositivos desde BD: {e}")
        
        # 3. Fallback a datos de emergencia
        fallback_data = api_cache.get_fallback_data(cache_key)
        if fallback_data:
            return ApiResponse(
                success=True,
                message=f"Dispositivos (fallback - puede estar desactualizado) - online_filter: {only_online}",
                data=fallback_data,
                timestamp=datetime.now()
            )
        
        # 4. Respuesta de emergencia para que Streamlit no falle
        logger.error("💥 No hay dispositivos disponibles en cache ni fallback")
        return ApiResponse(
            success=False,
            message="Temporalmente sin acceso a lista de dispositivos",
            data=[],  # Lista vacía en lugar de None
            timestamp=datetime.now()
        )

@app.get("/devices/{device_id}")
async def get_device_details(device_id: str):
    """Obtener detalles específicos de un dispositivo"""
    try:
        db_client = PooledPostgresClient()
        devices = db_client.get_devices()
        
        device = next((d for d in devices if d.get('device_id') == device_id), None)
        
        if not device:
            raise HTTPException(
                status_code=404,
                detail=f"Dispositivo {device_id} no encontrado"
            )
        
        # Obtener datos recientes del dispositivo
        recent_data = db_client.get_recent_data(device_id, limit=10)
        
        return ApiResponse(
            success=True,
            message=f"Detalles del dispositivo {device_id}",
            data={
                'device': device,
                'recent_data': recent_data
            },
            timestamp=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo detalles del dispositivo {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error obteniendo detalles del dispositivo"
        )


# Nuevo endpoint /data: retorna lista de registros recientes de sensor_data
from backend.postgres_client import PostgreSQLClient

@app.get("/data", response_model=ApiResponse)
async def get_latest_data(device_id: str = None, limit: int = 200, hours: float = None, days: int = None):
    """Obtener datos recientes con filtro temporal opcional y cache resiliente"""
    cache_key = CacheKeys.all_data(hours=hours, days=days, limit=limit)
    if device_id:
        cache_key = CacheKeys.device_data(device_id, limit=limit, hours=hours, days=days)
    
    # 1. Intentar cache fresco (TTL: 1 minuto para datos generales)
    cached_result = api_cache.get_cached_data(cache_key, ttl_override=60)
    if cached_result:
        time_desc = f"últimas {hours} horas" if hours else f"últimos {days} días" if days else f"últimos {limit} registros"
        return ApiResponse(
            success=True,
            message=f"Datos recientes (cache) ({time_desc})" + (f" para {device_id}" if device_id else ""),
            data=cached_result,
            timestamp=datetime.now()
        )
    
    # 2. Intentar base de datos
    try:
        db_client = PooledPostgresClient()
        
        if hours is not None:
            # Consulta por horas
            if device_id:
                data = db_client.get_data_by_hours(device_id, hours)
            else:
                data = db_client.get_all_data_by_hours(hours)
            time_desc = f"últimas {hours} horas"
        elif days is not None:
            # Consulta por días
            if device_id:
                data = db_client.get_data_by_days(device_id, days)
            else:
                data = db_client.get_all_data_by_days(days)
            time_desc = f"últimos {days} días"
        else:
            # Consulta por límite (comportamiento original)
            if device_id:
                data = db_client.execute_query(
                    "SELECT * FROM sensor_data WHERE device_id = %s ORDER BY timestamp DESC LIMIT %s", (device_id, limit)
                )
            else:
                data = db_client.execute_query(
                    "SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT %s", (limit,)
                )
            time_desc = f"últimos {limit} registros"

        # Guardar en cache para futuras consultas
        api_cache.set_cache_data(cache_key, data)

        return ApiResponse(
            success=True,
            message=f"Datos recientes ({time_desc})" + (f" para {device_id}" if device_id else ""),
            data=data,
            timestamp=datetime.now()
        )
    
    except Exception as e:
        logger.error(f"Error obteniendo datos recientes: {e}")
        
        # 3. Fallback a datos de emergencia
        fallback_data = api_cache.get_fallback_data(cache_key)
        if fallback_data:
            time_desc = f"últimas {hours} horas" if hours else f"últimos {days} días" if days else f"últimos {limit} registros"
            return ApiResponse(
                success=True,
                message=f"Datos recientes (fallback - puede estar desactualizado) ({time_desc})" + (f" para {device_id}" if device_id else ""),
                data=fallback_data,
                timestamp=datetime.now()
            )
        
        # 4. Respuesta de emergencia para que Streamlit no falle
        logger.error("💥 No hay datos recientes disponibles en cache ni fallback")
        return ApiResponse(
            success=False,
            message="Temporalmente sin acceso a datos recientes",
            data=[],  # Lista vacía en lugar de None
            timestamp=datetime.now()
        )

@app.get("/data/{device_id}")
async def get_device_data(device_id: str, limit: int = 100, hours: float = None, days: int = None):
    """Obtener datos históricos de un dispositivo específico con filtro temporal y cache resiliente"""
    cache_key = CacheKeys.device_data(device_id, limit, hours, days)
    
    # 1. Intentar cache fresco (TTL: 1 minuto para datos históricos)
    cached_result = api_cache.get_cached_data(cache_key, ttl_override=60)
    if cached_result:
        return ApiResponse(
            success=True,
            message=f"Datos históricos de {device_id} (cache)",
            data=cached_result,
            timestamp=datetime.now()
        )
    
    # 2. Intentar base de datos
    try:
        db_client = PooledPostgresClient()
        
        if hours is not None:
            # Consulta por horas
            data = db_client.get_data_by_hours(device_id, hours)
            time_desc = f"últimas {hours} horas"

            # Fallback robusto: si la ventana corta devuelve muy pocos puntos,
            # reintentar con 1 hora para garantizar visualización en tiempo real.
            try:
                if isinstance(hours, (int, float)) and float(hours) < 1.0 and (not data or len(data) <= 3):
                    data = db_client.get_data_by_hours(device_id, 1.0)
                    time_desc = "última 1 hora (fallback)"
            except Exception:
                pass
        elif days is not None:
            # Consulta por días  
            data = db_client.get_data_by_days(device_id, days)
            time_desc = f"últimos {days} días"
        else:
            # Consulta por límite (comportamiento original)
            data = db_client.get_recent_data(device_id, limit)
            time_desc = f"últimos {limit} registros"

        # Guardar en cache para futuras consultas
        api_cache.set_cache_data(cache_key, data)

        return ApiResponse(
            success=True,
            message=f"Datos históricos de {device_id} ({time_desc})",
            data=data,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de {device_id}: {e}")
        
        # 3. Fallback a datos de emergencia
        fallback_data = api_cache.get_fallback_data(cache_key)
        if fallback_data:
            return ApiResponse(
                success=True,
                message=f"Datos históricos de {device_id} (fallback - puede estar desactualizado)",
                data=fallback_data,
                timestamp=datetime.now()
            )
        
        # 4. Respuesta de emergencia para que Streamlit no falle
        logger.error(f"💥 No hay datos históricos disponibles para dispositivo {device_id}")
        return ApiResponse(
            success=False,
            message=f"Temporalmente sin acceso a datos del dispositivo {device_id}",
            data=[],  # Lista vacía en lugar de None
            timestamp=datetime.now()
        )

@app.post("/scan/network")
async def scan_network(background_tasks: BackgroundTasks):
    """Iniciar escaneo de red para nuevos dispositivos (resiliente)"""
    try:
        def run_scan():
            try:
                logger.info("Iniciando escaneo de red en segundo plano...")
                data_acquisition.device_scanner.scan_network()
                data_acquisition.arduino_detector.detect_ethernet_arduinos()
                logger.info("Escaneo de red completado")
            except Exception as scan_error:
                logger.error(f"Error durante escaneo de red: {scan_error}")
                # No lanzar excepción para no afectar la API
        
        background_tasks.add_task(run_scan)
        
        return ApiResponse(
            success=True,
            message="Escaneo de red iniciado en segundo plano",
            data={"status": "iniciado", "background_task": True},
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error iniciando escaneo de red: {e}")
        # Respuesta no crítica para que Streamlit no falle
        return ApiResponse(
            success=False,
            message="No se pudo iniciar escaneo de red en este momento",
            data={"status": "error", "error": str(e)},
            timestamp=datetime.now()
        )

@app.post("/acquisition/start")
async def start_acquisition(interval: int = 10):
    """Iniciar adquisición continua de datos (resiliente)"""
    global acquisition_task
    
    try:
        if data_acquisition.running:
            return ApiResponse(
                success=False,
                message="Adquisición ya está en ejecución",
                data={"status": "ya_ejecutandose", "interval": interval},
                timestamp=datetime.now()
            )
        
        # Iniciar en thread separado para no bloquear la API
        def run_acquisition():
            try:
                data_acquisition.start_continuous_acquisition(interval)
            except Exception as acq_error:
                logger.error(f"Error durante adquisición continua: {acq_error}")
                # Reintentar automáticamente después de delay
                import time
                time.sleep(5)
                try:
                    data_acquisition.start_continuous_acquisition(interval)
                except Exception as retry_error:
                    logger.error(f"Error en reintento de adquisición: {retry_error}")
        
        import threading
        acquisition_task = threading.Thread(target=run_acquisition, daemon=True)
        acquisition_task.start()
        
        return ApiResponse(
            success=True,
            message=f"Adquisición iniciada con intervalo de {interval} segundos",
            data={"status": "iniciada", "interval": interval, "thread_daemon": True},
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error iniciando adquisición: {e}")
        # Respuesta no crítica para que Streamlit no falle
        return ApiResponse(
            success=False,
            message="No se pudo iniciar adquisición en este momento",
            data={"status": "error", "error": str(e), "interval": interval},
            timestamp=datetime.now()
        )

@app.post("/acquisition/stop")
async def stop_acquisition():
    """Detener adquisición continua de datos (resiliente)"""
    global acquisition_task
    
    try:
        data_acquisition.stop_acquisition()
        acquisition_task = None
        
        return ApiResponse(
            success=True,
            message="Adquisición detenida correctamente",
            data={"status": "detenida"},
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error deteniendo adquisición: {e}")
        # Respuesta no crítica para que Streamlit no falle
        return ApiResponse(
            success=False,
            message="No se pudo detener adquisición - puede ya estar detenida",
            data={"status": "error", "error": str(e)},
            timestamp=datetime.now()
        )

@app.post("/data/collect")
async def collect_data_now():
    """Recopilar datos inmediatamente (una vez) - operación resiliente"""
    try:
        data = data_acquisition.collect_all_data()
        
        return ApiResponse(
            success=True,
            message="Datos recopilados correctamente",
            data=data,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error recopilando datos: {e}")
        # Respuesta no crítica para que Streamlit no falle
        return ApiResponse(
            success=False,
            message="No se pudieron recopilar datos en este momento",
            data={"status": "error", "error": str(e)},
            timestamp=datetime.now()
        )


@app.post("/debug/frontend_ping")
async def frontend_ping(request: dict = None):
    """Endpoint usado por frontend para dejar evidencia de que la UI está viva y llamó al backend.
    Registra un evento en la tabla system_events con IP y user-agent.
    """
    try:
        db_client = PooledPostgresClient()
        # Intentar obtener información del request desde FastAPI (headers en starlette)
        from fastapi import Request
        # Si el caller envía un JSON con metadata, lo usamos
        metadata = request if isinstance(request, dict) else {}
        # Registrar evento con origen y metadata
        # Tratar de extraer información de cabeceras si se provee en metadata
        origin = metadata.get('origin') if isinstance(metadata, dict) else None
        ua = metadata.get('user_agent') if isinstance(metadata, dict) else None

        # Registrar en system_events
        db_client.log_system_event(
            event_type='frontend_ping',
            device_id=None,
            message='Frontend Ping recibido',
            metadata={'origin': origin, 'user_agent': ua}
        )

        return {"success": True, "message": "Ping registrado"}
    except Exception as e:
        logger.error(f"Error en frontend_ping: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs/system")
async def get_system_logs(limit: int = 50):
    """Obtener logs recientes del sistema"""
    try:
        db_client = PooledPostgresClient()
        logs = db_client.get_system_events(limit)
        
        return ApiResponse(
            success=True,
            message=f"Últimos {limit} eventos del sistema",
            data=logs,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo logs del sistema: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error obteniendo logs del sistema"
        )




# Función principal para ejecutar el servidor
def run_api_server():
    """Ejecutar servidor API con configuración por defecto"""
    host = "0.0.0.0"
    port = 8000
    logger.info(f"Iniciando servidor API en {host}:{port}")
    uvicorn.run(
        "backend.api:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    run_api_server()
