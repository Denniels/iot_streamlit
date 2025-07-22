"""
API REST con FastAPI para el backend IoT
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uvicorn
from datetime import datetime
import asyncio

from backend.config import get_logger, IOT_CONFIG
from backend.data_acquisition import DataAcquisition
from backend.db_writer import SupabaseClient

# Configuración de logging
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

# Instancia global del sistema de adquisición
data_acquisition = DataAcquisition()
acquisition_task = None

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
        # Inicializar detectores de dispositivos
        data_acquisition.initialize_devices()
        logger.info("Sistema inicializado correctamente")
        
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
        timestamp=datetime.now()
    )

@app.get("/health")
async def health_check():
    """Verificación de salud del sistema"""
    try:
        db_client = SupabaseClient()
        # Probar conexión a base de datos
        devices = db_client.get_devices()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(),
            "database": "connected",
            "devices_count": len(devices)
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Sistema no saludable: {str(e)}"
        )

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
async def get_devices():
    """Obtener lista de todos los dispositivos detectados"""
    try:
        db_client = SupabaseClient()
        devices = db_client.get_devices()
        
        # Formatear información de dispositivos
        formatted_devices = []
        for device in devices:
            formatted_devices.append({
                'device_id': device.get('device_id'),
                'device_type': device.get('device_type'),
                'ip_address': device.get('ip_address'),
                'port': device.get('port'),
                'status': device.get('status'),
                'last_seen': device.get('last_seen'),
                'description': device.get('description')
            })
        
        return ApiResponse(
            success=True,
            message=f"{len(formatted_devices)} dispositivos encontrados",
            data=formatted_devices,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo dispositivos: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error obteniendo lista de dispositivos"
        )

@app.get("/devices/{device_id}")
async def get_device_details(device_id: str):
    """Obtener detalles específicos de un dispositivo"""
    try:
        db_client = SupabaseClient()
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

@app.get("/data", response_model=ApiResponse)
async def get_latest_data():
    """Obtener los datos más recientes de todos los dispositivos"""
    try:
        data = data_acquisition.get_latest_data()
        
        return ApiResponse(
            success=True,
            message="Datos más recientes obtenidos",
            data=data,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo datos recientes: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error obteniendo datos recientes"
        )

@app.get("/data/{device_id}")
async def get_device_data(device_id: str, limit: int = 100):
    """Obtener datos históricos de un dispositivo específico"""
    try:
        db_client = SupabaseClient()
        data = db_client.get_recent_data(device_id, limit)
        
        return ApiResponse(
            success=True,
            message=f"Datos históricos de {device_id} (últimos {limit})",
            data=data,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error obteniendo datos de {device_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo datos del dispositivo {device_id}"
        )

@app.post("/scan/network")
async def scan_network(background_tasks: BackgroundTasks):
    """Iniciar escaneo de red para nuevos dispositivos"""
    try:
        def run_scan():
            logger.info("Iniciando escaneo de red en segundo plano...")
            data_acquisition.device_scanner.scan_network()
            data_acquisition.arduino_detector.detect_ethernet_arduinos()
            logger.info("Escaneo de red completado")
        
        background_tasks.add_task(run_scan)
        
        return ApiResponse(
            success=True,
            message="Escaneo de red iniciado en segundo plano",
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error iniciando escaneo de red: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error iniciando escaneo de red"
        )

@app.post("/acquisition/start")
async def start_acquisition(interval: int = 10):
    """Iniciar adquisición continua de datos"""
    global acquisition_task
    
    try:
        if data_acquisition.running:
            return ApiResponse(
                success=False,
                message="Adquisición ya está en ejecución",
                timestamp=datetime.now()
            )
        
        # Iniciar en thread separado para no bloquear la API
        def run_acquisition():
            data_acquisition.start_continuous_acquisition(interval)
        
        import threading
        acquisition_task = threading.Thread(target=run_acquisition, daemon=True)
        acquisition_task.start()
        
        return ApiResponse(
            success=True,
            message=f"Adquisición iniciada con intervalo de {interval} segundos",
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error iniciando adquisición: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error iniciando adquisición de datos"
        )

@app.post("/acquisition/stop")
async def stop_acquisition():
    """Detener adquisición continua de datos"""
    global acquisition_task
    
    try:
        data_acquisition.stop_acquisition()
        acquisition_task = None
        
        return ApiResponse(
            success=True,
            message="Adquisición detenida correctamente",
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error deteniendo adquisición: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error deteniendo adquisición de datos"
        )

@app.post("/data/collect")
async def collect_data_now():
    """Recopilar datos inmediatamente (una vez)"""
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
        raise HTTPException(
            status_code=500,
            detail="Error recopilando datos"
        )

@app.get("/logs/system")
async def get_system_logs(limit: int = 50):
    """Obtener logs recientes del sistema"""
    try:
        db_client = SupabaseClient()
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
    """Ejecutar servidor API con configuración"""
    host = IOT_CONFIG.get('api_host', '0.0.0.0')
    port = IOT_CONFIG.get('api_port', 8000)
    
    logger.info(f"Iniciando servidor API en {host}:{port}")
    
    uvicorn.run(
        "backend.api:app",
        host=host,
        port=port,
        reload=False,  # En producción no usar reload
        log_level="info"
    )

if __name__ == "__main__":
    run_api_server()
