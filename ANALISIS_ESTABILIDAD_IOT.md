# Análisis de Estabilidad y Soluciones Robustas - Sistema IoT Streamlit

## Resumen Ejecutivo

Tras el análisis completo del proyecto, se han identificado múltiples puntos de falla que causan la inestabilidad observada en el sistema. El problema principal radica en la falta de mecanismos robustos de recuperación en el **backend de la Jetson Nano**, timeouts agresivos, reconexión automática limitada y dependencias frágiles entre los servicios systemd.

### Arquitectura del Sistema:
- **Frontend**: Streamlit Cloud (externo, limitaciones de persistencia)
- **Backend**: Jetson Nano con 4 servicios systemd en red local
- **Dispositivos**: Conectados a red local (ESP32, Arduino Ethernet)
- **Conexión**: Cloudflare Tunnel expone API local al frontend cloud

### Estado Actual: 🔴 INESTABLE
- **Frontend Streamlit Cloud**: Pérdida intermitente de conexión con API
- **Backend Jetson Nano**: Errores de timeout sin recuperación automática
- **Cloudflare Tunnel**: Reconexión manual requerida, URLs obsoletas
- **Base de datos PostgreSQL**: Transacciones abortadas sin recovery
- **Servicios systemd**: Oscilación entre estados online/offline

---

## 🔍 Análisis de Causas Raíz

### 1. **PROBLEMAS DEL FRONTEND (Streamlit Cloud - LIMITACIONES)**

#### Limitaciones de Streamlit Cloud:
```python
# ❌ LIMITACIÓN: Sin persistencia local en Streamlit Cloud
# No se puede guardar cache en archivos locales
# No se pueden instalar dependencias del sistema
# Timeouts de la plataforma no controlables

# ❌ PROBLEMA: Timeout fijo sin control del lado cloud
resp = requests.get(url, timeout=10)  # Streamlit Cloud puede interrumpir antes
```

#### Impacto y Restricciones:
- **Sin cache persistente** en Streamlit Cloud (solo session_state)
- **Timeouts externos** de la plataforma cloud no controlables
- **Reintentos limitados** por restricciones de tiempo de ejecución
- **Dependencia total** del backend para estabilidad

**✅ ESTRATEGIA**: Todas las soluciones de estabilidad deben implementarse en el **backend de la Jetson Nano**

### 2. **PROBLEMAS CRÍTICOS DEL BACKEND (Jetson Nano - SOLUCIONABLE)**

#### Problemas en Servicios systemd:
```bash
# ❌ PROBLEMA: Servicios sin dependencias correctas
[Unit]
Description=Servicio de adquisición de datos
After=network.target  # ← Debería esperar PostgreSQL y API

# ❌ PROBLEMA: Sin health checks entre servicios
# acquire_data.service no verifica que backend_api esté funcionando
# start_cloudflare_py.service no verifica que la API responda
```

#### Problemas en Conexiones PostgreSQL:
```python
# ❌ PROBLEMA: Sin connection pooling en PostgreSQL
def __init__(self):
    self.conn = psycopg2.connect(...)  # Una sola conexión global

# ❌ PROBLEMA: Reconexión manual y limitada
if "current transaction is aborted" in str(e):
    if self._reconnect():  # Solo 1 intento de reconexión
        try:
            # Reintenta UNA vez
```

#### Problemas en API FastAPI:
```python
# ❌ PROBLEMA: Sin circuit breaker ni rate limiting
@app.get("/data/{device_id}")
async def get_device_data(device_id: str):
    # Sin protección contra consultas pesadas concurrentes
    # Sin cache interno para datos frecuentemente solicitados
```

#### Impacto:
- **Conexiones BD perdidas** causan fallo total del sistema
- **Transacciones abortadas** requieren reinicio manual del servicio
- **Sin coordinación** entre servicios systemd
- **Consultas concurrentes** desde Streamlit Cloud sobrecargan el sistema

### 3. **PROBLEMAS DE CLOUDFLARE TUNNEL (Jetson Nano)**

#### Problemas en start_cloudflare.py:
```python
# ❌ PROBLEMA: Sin monitoreo de salud del túnel
process = subprocess.Popen([CLOUDFLARED_BIN, 'tunnel', '--url', BACKEND_URL])
# No hay verificación de que el túnel sigue funcionando

# ❌ PROBLEMA: URL detectada una sola vez al inicio
if not url_found:
    match = tunnel_url_re.search(line)
    if match:
        url = match.group(0)
        url_found = True  # ← No vuelve a detectar cambios de URL

# ❌ PROBLEMA: Sin notificación a API cuando URL cambia
# La API sigue devolviendo URL obsoleta en /cf_url
```

#### Impacto:
- **URLs obsoletas** cuando el túnel se recrea (Streamlit Cloud no puede conectar)
- **Sin detección automática** de reconexiones del túnel
- **Fallos silenciosos** del túnel sin alertas en logs
- **Descoordinación** entre servicio tunnel y API

### 4. **PROBLEMAS DE SINCRONIZACIÓN DE DATOS**

#### Problemas Identificados:
```python
# ❌ PROBLEMA: Lógica de "online" basada en timestamps inconsistentes
dev['online'] = (now - last_dt) <= timedelta(minutes=5)

# ❌ PROBLEMA: Sin heartbeat entre componentes
# No hay ping periódico para verificar conectividad real
```

#### Impacto:
- **Estados inconsistentes** entre componentes
- **Dispositivos marcados como offline** aunque estén enviando datos
- **Datos aparecen y desaparecen** según timing de consultas

---

## 🛠️ Soluciones Robustas Implementables (Backend Jetson Nano)

### **SOLUCIÓN 1: API FastAPI Resiliente con Cache Interno**

```python
# ✅ SOLUCIÓN: Cache interno en la API (Jetson Nano)
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class APIInternalCache:
    """Cache interno en la API para servir datos incluso cuando PostgreSQL falla"""
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutos
        self.fallback_data = {}  # Datos de emergencia
        
    def get_cached_data(self, key: str) -> Optional[Dict]:
        """Obtiene datos del cache si están frescos"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                return data
        return None
    
    def set_cache_data(self, key: str, data: Dict):
        """Guarda datos en cache con timestamp"""
        self.cache[key] = (data, datetime.now())
        # También guardar como fallback persistente
        self.fallback_data[key] = data
        self._persist_fallback()
    
    def get_fallback_data(self, key: str) -> Optional[Dict]:
        """Obtiene datos de emergencia cuando todo falla"""
        return self.fallback_data.get(key)
    
    def _persist_fallback(self):
        """Guarda datos de emergencia en disco (Jetson Nano)"""
        try:
            with open('/tmp/iot_api_fallback.json', 'w') as f:
                json.dump(self.fallback_data, f, default=str)
        except Exception:
            pass  # No bloquear si falla la persistencia

# ✅ IMPLEMENTACIÓN: Endpoints resilientes con cache interno
api_cache = APIInternalCache()

@app.get("/data/{device_id}")
async def get_device_data_resilient(device_id: str, hours: float = None):
    """Endpoint resiliente con cache interno y fallback"""
    cache_key = f"device_data_{device_id}_{hours or 'recent'}"
    
    # 1. Intentar cache fresco
    cached = api_cache.get_cached_data(cache_key)
    if cached:
        logger.debug(f"✅ Serving cached data for {device_id}")
        return ApiResponse(
            success=True,
            message=f"Datos de {device_id} (cache)",
            data=cached,
            timestamp=datetime.now()
        )
    
    # 2. Intentar base de datos con retry
    try:
        db_client = LocalPostgresClient()
        if hours:
            data = db_client.get_data_by_hours(device_id, hours)
        else:
            data = db_client.get_recent_data(device_id, 100)
        
        # Guardar en cache si exitoso
        api_cache.set_cache_data(cache_key, data)
        
        return ApiResponse(
            success=True,
            message=f"Datos de {device_id} (database)",
            data=data,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"❌ Database failed for {device_id}: {e}")
        
        # 3. Fallback a datos de emergencia
        fallback = api_cache.get_fallback_data(cache_key)
        if fallback:
            logger.warning(f"⚠️ Using fallback data for {device_id}")
            return ApiResponse(
                success=True,
                message=f"Datos de {device_id} (fallback - puede estar desactualizado)",
                data=fallback,
                timestamp=datetime.now()
            )
        
        # 4. Error total - devolver estructura mínima para que Streamlit no falle
        logger.error(f"💥 No data available for {device_id}")
        return ApiResponse(
            success=False,
            message=f"Temporalmente sin datos para {device_id}",
            data=[],  # Lista vacía en lugar de None
            timestamp=datetime.now()
        )

# ✅ IMPLEMENTACIÓN: Health check avanzado con datos cached
@app.get("/health/detailed")
async def health_check_detailed():
    """Health check detallado que siempre responde"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "cache_stats": {},
        "fallback_available": bool(api_cache.fallback_data)
    }
    
    # Test database (no bloquear si falla)
    try:
        db_client = LocalPostgresClient()
        devices = db_client.get_devices()
        health_status["services"]["database"] = {
            "status": "healthy",
            "devices_count": len(devices)
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "degraded",
            "error": str(e)[:100]
        }
        health_status["status"] = "degraded"
    
    # Cache statistics
    health_status["cache_stats"] = {
        "cached_keys": len(api_cache.cache),
        "fallback_keys": len(api_cache.fallback_data)
    }
    
    return health_status
```

### **SOLUCIÓN 2: PostgreSQL con Connection Pooling Robusto (Jetson Nano)**

```python
# ✅ SOLUCIÓN: Connection pooling robusto en Jetson Nano
from psycopg2 import pool
import threading
import time
import os

class RobustPostgresClient:
    """Cliente PostgreSQL con connection pooling y auto-recovery para Jetson Nano"""
    
    def __init__(self):
        self.connection_pool = None
        self.pool_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.health_monitor_running = False
        self._initialize_pool()
        self._start_health_monitor()
    
    def _initialize_pool(self):
        """Inicializa pool de conexiones con configuración optimizada para Jetson Nano"""
        for attempt in range(self.max_reconnect_attempts):
            try:
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,  # Mínimo para Jetson Nano (recursos limitados)
                    maxconn=5,  # Máximo para Jetson Nano (balance performance/recursos)
                    dbname=os.getenv('DB_NAME', 'iot_db'),
                    user=os.getenv('DB_USER', 'iot_user'),
                    password=os.getenv('DB_PASSWORD', 'DAms15820'),
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    connect_timeout=15,  # Timeout más generoso
                    application_name='iot_jetson_pool',
                    # Configuraciones específicas para estabilidad
                    keepalives_idle=600,        # 10 minutos
                    keepalives_interval=30,     # 30 segundos
                    keepalives_count=3          # 3 intentos
                )
                logger.info(f"✅ Pool PostgreSQL inicializado en Jetson Nano (intento {attempt+1})")
                self.reconnect_attempts = 0
                return True
            except Exception as e:
                logger.error(f"❌ Error inicializando pool (intento {attempt+1}): {e}")
                if attempt < self.max_reconnect_attempts - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.critical("💥 CRITICAL: No se pudo inicializar PostgreSQL en Jetson Nano")
                    self.connection_pool = None
                    return False
    
    def _start_health_monitor(self):
        """Inicia monitor de salud que verifica conexiones cada 60 segundos"""
        def health_monitor():
            self.health_monitor_running = True
            while self.health_monitor_running:
                try:
                    if self.connection_pool:
                        # Test simple de conectividad
                        result = self.execute_with_retry("SELECT 1 as health_check", max_retries=1)
                        if not result:
                            logger.warning("⚠️ Health check falló, reinicializando pool...")
                            self._close_pool()
                            self._initialize_pool()
                    else:
                        logger.warning("⚠️ Pool no disponible, intentando reinicializar...")
                        self._initialize_pool()
                except Exception as e:
                    logger.error(f"Error en health monitor: {e}")
                
                time.sleep(60)  # Check cada minuto
        
        thread = threading.Thread(target=health_monitor, daemon=True)
        thread.start()
        logger.info("💓 PostgreSQL health monitor iniciado en Jetson Nano")

# ✅ IMPLEMENTACIÓN: Cliente global optimizado para Jetson Nano
# Reemplazar LocalPostgresClient con RobustPostgresClient
def get_robust_db_client():
    """Factory para obtener cliente robusto (singleton para Jetson Nano)"""
    if not hasattr(get_robust_db_client, 'instance'):
        get_robust_db_client.instance = RobustPostgresClient()
    return get_robust_db_client.instance
```

### **SOLUCIÓN 3: Cloudflare Tunnel Auto-Recovery (Jetson Nano)**

```python
# ✅ SOLUCIÓN: Tunnel resiliente con auto-recovery en systemd service
import subprocess
import time
import requests
import threading
import signal
import sys
from datetime import datetime, timedelta

class JetsonCloudflareManager:
    """Manager de Cloudflare Tunnel optimizado para Jetson Nano con systemd"""
    
    def __init__(self):
        self.current_url = None
        self.process = None
        self.monitoring = False
        self.restart_count = 0
        self.last_restart = None
        self.api_notification_url = "http://localhost:8000/internal/tunnel_url_update"
        
        # Configurar signal handlers para systemd
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def start_tunnel_with_monitoring(self):
        """Inicia túnel con monitoreo optimizado para Jetson Nano"""
        self.monitoring = True
        
        # Thread para gestionar el proceso del túnel
        tunnel_thread = threading.Thread(target=self._manage_tunnel_process, daemon=False)
        tunnel_thread.start()
        
        # Thread para monitorear salud del túnel
        monitor_thread = threading.Thread(target=self._monitor_tunnel_health, daemon=True)
        monitor_thread.start()
        
        logger.info("🌐 Cloudflare Tunnel Manager iniciado en Jetson Nano")
        
        # Mantener hilo principal vivo para systemd
        try:
            tunnel_thread.join()
        except KeyboardInterrupt:
            self.stop()
    
    def _manage_tunnel_process(self):
        """Gestiona el proceso del túnel con auto-restart optimizado para Jetson"""
        while self.monitoring:
            try:
                logger.info("🚀 Iniciando cloudflared en Jetson Nano...")
                
                # Comando optimizado para Jetson Nano
                cmd = [
                    '/usr/local/bin/cloudflared', 
                    'tunnel', 
                    '--url', 'http://localhost:8000',
                    '--no-autoupdate',
                    '--retries', '3',
                    '--retry-backoff', '5s'
                ]
                
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Capturar URL del túnel y notificar a API
                url_detected = False
                for line in self.process.stdout:
                    logger.info(f"CF: {line.strip()}")
                    
                    if not url_detected:
                        match = re.search(r'https://[\w-]+\.trycloudflare\.com', line)
                        if match:
                            new_url = match.group(0)
                            if new_url != self.current_url:
                                self.current_url = new_url
                                self._update_secrets_file(new_url)
                                self._notify_api_new_url(new_url)  # ← NUEVO
                                logger.info(f"✅ Nueva URL detectada: {new_url}")
                            url_detected = True
                
                # El proceso terminó
                return_code = self.process.wait()
                logger.warning(f"⚠️ cloudflared terminó con código: {return_code}")
                
                # Determinar si reiniciar automáticamente
                if self.monitoring:
                    # Backoff más conservador para Jetson Nano
                    restart_delay = min(120, 10 * (self.restart_count + 1))  # Max 2 min
                    logger.info(f"🔄 Reiniciando túnel en {restart_delay}s...")
                    time.sleep(restart_delay)
                    self.restart_count += 1
                    self.last_restart = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Error en túnel: {e}")
                if self.monitoring:
                    time.sleep(30)  # Pausa más larga en caso de error
    
    def _notify_api_new_url(self, new_url):
        """Notifica a la API FastAPI sobre nueva URL del túnel"""
        try:
            payload = {
                "new_url": new_url,
                "timestamp": datetime.now().isoformat(),
                "source": "tunnel_manager"
            }
            response = requests.post(
                self.api_notification_url, 
                json=payload, 
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"✅ API notificada sobre nueva URL: {new_url}")
            else:
                logger.warning(f"⚠️ API no pudo ser notificada: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Error notificando API: {e}")
    
    def _monitor_tunnel_health(self):
        """Monitorea la salud del túnel optimizado para recursos de Jetson"""
        consecutive_failures = 0
        check_interval = 45  # 45 segundos (menos frecuente para Jetson)
        
        while self.monitoring:
            try:
                if self.current_url:
                    # Test del endpoint de salud con timeout generoso
                    response = requests.get(f"{self.current_url}/health", timeout=15)
                    if response.status_code == 200:
                        consecutive_failures = 0
                        logger.debug(f"✅ Tunnel health OK: {self.current_url}")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Tunnel response {response.status_code}")
                else:
                    consecutive_failures += 1
                    logger.warning("⚠️ No hay URL de túnel disponible")
                
                # Si hay muchos fallos, forzar restart (más tolerante para Jetson)
                if consecutive_failures >= 8:  # 6 minutos de fallos
                    logger.error(f"💥 Túnel inaccesible ({consecutive_failures} fallos), reiniciando proceso...")
                    self._force_restart()
                    consecutive_failures = 0
                
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"⚠️ Health check falló: {e}")
            
            time.sleep(check_interval)
    
    def _signal_handler(self, signum, frame):
        """Handler para señales de systemd"""
        logger.info(f"📡 Señal recibida: {signum}, cerrando túnel...")
        self.stop()
        sys.exit(0)
    
    def stop(self):
        """Detiene el manager del túnel de forma limpia"""
        self.monitoring = False
        self._force_restart()
        logger.info("🛑 Cloudflare Tunnel Manager detenido")

# ✅ IMPLEMENTACIÓN: Endpoint interno para recibir notificaciones de URL
@app.post("/internal/tunnel_url_update")
async def update_tunnel_url(request: dict):
    """Endpoint interno para recibir actualizaciones de URL del tunnel manager"""
    try:
        new_url = request.get("new_url")
        if new_url:
            # Actualizar secrets_tunnel.toml desde la API
            secrets_data = {'cloudflare': {'url': new_url}}
            secrets_path = os.path.join(os.path.dirname(__file__), '../secrets_tunnel.toml')
            with open(secrets_path, 'w') as f:
                toml.dump(secrets_data, f)
            
            logger.info(f"📝 secrets_tunnel.toml actualizado desde API: {new_url}")
            return {"success": True, "message": "URL actualizada"}
        else:
            return {"success": False, "error": "No URL provided"}
    except Exception as e:
        logger.error(f"Error actualizando URL desde tunnel manager: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Para uso como servicio systemd
    manager = JetsonCloudflareManager()
    manager.start_tunnel_with_monitoring()
```

### **SOLUCIÓN 4: Servicios systemd Coordinados (Jetson Nano)**

```ini
# ✅ ARCHIVO: /etc/systemd/system/iot-postgresql.service
# Servicio base que debe iniciarse primero
[Unit]
Description=PostgreSQL para IoT en Jetson Nano
After=network.target

[Service]
Type=simple
User=postgres
ExecStart=/usr/lib/postgresql/10/bin/postgres -D /var/lib/postgresql/10/main -c config_file=/etc/postgresql/10/main/postgresql.conf
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# ✅ ARCHIVO: /etc/systemd/system/iot-backend-api.service  
# API que depende de PostgreSQL
[Unit]
Description=API Backend IoT para Jetson Nano
After=network.target iot-postgresql.service
Wants=iot-postgresql.service
Requires=iot-postgresql.service

[Service]
Type=simple
User=daniel
WorkingDirectory=/home/daniel/repos/iot_streamlit
Environment="VIRTUAL_ENV=/home/daniel/repos/iot_streamlit/.iot_streamlit"
Environment="PATH=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/bin/sleep 10
ExecStart=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin/python -c "from backend.api import run_api_server; run_api_server()"
Restart=always
RestartSec=15
# Health check cada 30 segundos
ExecReload=/bin/kill -HUP $MAINPID

[Install]
WantedBy=multi-user.target

# ✅ ARCHIVO: /etc/systemd/system/iot-tunnel.service
# Túnel que depende de API
[Unit]
Description=Cloudflare Tunnel para IoT Jetson Nano
After=network.target iot-backend-api.service
Wants=iot-backend-api.service
Requires=iot-backend-api.service

[Service]
Type=simple
User=daniel
WorkingDirectory=/home/daniel/repos/iot_streamlit
Environment="VIRTUAL_ENV=/home/daniel/repos/iot_streamlit/.iot_streamlit"
Environment="PATH=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/bin/sleep 15
ExecStart=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin/python /home/daniel/repos/iot_streamlit/start_cloudflare_resilient.py
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target

# ✅ ARCHIVO: /etc/systemd/system/iot-data-acquisition.service
# Adquisición que depende de API y BD
[Unit]
Description=Adquisición de datos IoT Jetson Nano
After=network.target iot-backend-api.service iot-postgresql.service
Wants=iot-backend-api.service iot-postgresql.service
Requires=iot-postgresql.service

[Service]
Type=simple
User=daniel
WorkingDirectory=/home/daniel/repos/iot_streamlit
Environment="VIRTUAL_ENV=/home/daniel/repos/iot_streamlit/.iot_streamlit"
Environment="PATH=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStartPre=/bin/sleep 20
ExecStart=/home/daniel/repos/iot_streamlit/.iot_streamlit/bin/python /home/daniel/repos/iot_streamlit/acquire_data.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **SOLUCIÓN 2: Backend con Connection Pooling y Auto-Recovery**

```python
# ✅ SOLUCIÓN: Connection pooling robusto
from psycopg2 import pool
import threading
import time

class RobustPostgresClient:
    def __init__(self):
        self.connection_pool = None
        self.pool_lock = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Inicializa pool de conexiones con retry automático"""
        for attempt in range(self.max_reconnect_attempts):
            try:
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    dbname=os.getenv('DB_NAME', 'iot_db'),
                    user=os.getenv('DB_USER', 'iot_user'),
                    password=os.getenv('DB_PASSWORD', 'DAms15820'),
                    host=os.getenv('DB_HOST', 'localhost'),
                    port=os.getenv('DB_PORT', '5432'),
                    connect_timeout=10,
                    application_name='iot_backend_pool'
                )
                logger.info(f"✅ Pool de conexiones PostgreSQL inicializado (intento {attempt+1})")
                self.reconnect_attempts = 0
                return True
            except Exception as e:
                logger.error(f"❌ Error inicializando pool (intento {attempt+1}): {e}")
                if attempt < self.max_reconnect_attempts - 1:
                    time.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    logger.critical("💥 No se pudo inicializar pool de conexiones PostgreSQL")
                    self.connection_pool = None
                    return False
    
    def execute_with_retry(self, query, params=None, max_retries=3):
        """Ejecuta consulta con retry automático y manejo de errores"""
        if not self.connection_pool:
            if not self._initialize_pool():
                return []
        
        for attempt in range(max_retries):
            conn = None
            try:
                with self.pool_lock:
                    conn = self.connection_pool.getconn()
                
                with conn.cursor() as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    
                    if query.strip().upper().startswith('SELECT'):
                        columns = [desc[0] for desc in cur.description]
                        rows = cur.fetchall()
                        result = [dict(zip(columns, row)) for row in rows]
                    else:
                        conn.commit()
                        result = cur.rowcount
                
                # Devolver conexión al pool
                with self.pool_lock:
                    self.connection_pool.putconn(conn)
                
                return result
                
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                logger.warning(f"⚠️ Error de conexión (intento {attempt+1}): {e}")
                
                # Marcar conexión como inválida
                if conn:
                    with self.pool_lock:
                        self.connection_pool.putconn(conn, close=True)
                
                # Reinicializar pool si es necesario
                if "server closed the connection" in str(e) or "connection is closed" in str(e):
                    logger.info("🔄 Reinicializando pool de conexiones...")
                    self._close_pool()
                    if not self._initialize_pool():
                        time.sleep(2 ** attempt)
                        continue
                
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                else:
                    logger.error(f"💥 Query falló después de {max_retries} intentos: {query[:100]}")
                    return []
                    
            except Exception as e:
                logger.error(f"❌ Error inesperado en query: {e}")
                if conn:
                    with self.pool_lock:
                        self.connection_pool.putconn(conn)
                return []
        
        return []
    
    def _close_pool(self):
        """Cierra pool de conexiones de manera segura"""
        try:
            if self.connection_pool:
                self.connection_pool.closeall()
                self.connection_pool = None
        except Exception as e:
            logger.error(f"Error cerrando pool: {e}")

# ✅ IMPLEMENTACIÓN: Health check automático
class HealthMonitor:
    def __init__(self, db_client):
        self.db_client = db_client
        self.health_status = {
            'database': False,
            'last_check': None,
            'consecutive_failures': 0
        }
        self.start_monitoring()
    
    def start_monitoring(self):
        """Inicia monitoreo continuo de salud del sistema"""
        def monitor_loop():
            while True:
                try:
                    # Test database
                    result = self.db_client.execute_with_retry("SELECT 1 as test")
                    if result and len(result) > 0:
                        self.health_status['database'] = True
                        self.health_status['consecutive_failures'] = 0
                    else:
                        self.health_status['database'] = False
                        self.health_status['consecutive_failures'] += 1
                    
                    self.health_status['last_check'] = datetime.now()
                    
                    # Alert si hay muchos fallos consecutivos
                    if self.health_status['consecutive_failures'] >= 5:
                        logger.critical(f"🚨 Sistema inestable: {self.health_status['consecutive_failures']} fallos consecutivos")
                        # Aquí se podría enviar una notificación
                        
                except Exception as e:
                    logger.error(f"Error en health check: {e}")
                    self.health_status['database'] = False
                    self.health_status['consecutive_failures'] += 1
                
                time.sleep(30)  # Check cada 30 segundos
        
        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()
        logger.info("🏥 Health monitor iniciado")
```

### **SOLUCIÓN 3: Cloudflare Tunnel Auto-Recovery**

```python
# ✅ SOLUCIÓN: Tunnel resiliente con auto-recovery
import subprocess
import time
import requests
import threading
from datetime import datetime, timedelta

class ResilientCloudflareManager:
    def __init__(self):
        self.current_url = None
        self.process = None
        self.monitoring = False
        self.restart_count = 0
        self.last_restart = None
        
    def start_tunnel_with_monitoring(self):
        """Inicia túnel con monitoreo y auto-restart"""
        self.monitoring = True
        
        # Thread para gestionar el proceso del túnel
        tunnel_thread = threading.Thread(target=self._manage_tunnel_process, daemon=True)
        tunnel_thread.start()
        
        # Thread para monitorear salud del túnel
        monitor_thread = threading.Thread(target=self._monitor_tunnel_health, daemon=True)
        monitor_thread.start()
        
        logger.info("🌐 Cloudflare Tunnel Manager iniciado con auto-recovery")
    
    def _manage_tunnel_process(self):
        """Gestiona el proceso del túnel con auto-restart"""
        while self.monitoring:
            try:
                logger.info("🚀 Iniciando cloudflared...")
                
                self.process = subprocess.Popen(
                    ['/usr/local/bin/cloudflared', 'tunnel', '--url', 'http://localhost:8000', '--no-autoupdate'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Capturar URL del túnel
                url_detected = False
                for line in self.process.stdout:
                    logger.info(f"CF: {line.strip()}")
                    
                    if not url_detected:
                        match = re.search(r'https://[\w-]+\.trycloudflare\.com', line)
                        if match:
                            new_url = match.group(0)
                            if new_url != self.current_url:
                                self.current_url = new_url
                                self._update_secrets_file(new_url)
                                logger.info(f"✅ Nueva URL detectada: {new_url}")
                            url_detected = True
                
                # El proceso terminó
                return_code = self.process.wait()
                logger.warning(f"⚠️ cloudflared terminó con código: {return_code}")
                
                # Determinar si reiniciar automáticamente
                if self.monitoring:
                    restart_delay = min(60, 5 * (self.restart_count + 1))  # Max 60s
                    logger.info(f"🔄 Reiniciando túnel en {restart_delay}s...")
                    time.sleep(restart_delay)
                    self.restart_count += 1
                    self.last_restart = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Error en túnel: {e}")
                if self.monitoring:
                    time.sleep(10)
    
    def _monitor_tunnel_health(self):
        """Monitorea la salud del túnel haciendo requests periódicos"""
        consecutive_failures = 0
        
        while self.monitoring:
            try:
                if self.current_url:
                    # Test del endpoint de salud
                    response = requests.get(f"{self.current_url}/health", timeout=10)
                    if response.status_code == 200:
                        consecutive_failures = 0
                        logger.debug(f"✅ Tunnel health OK: {self.current_url}")
                    else:
                        consecutive_failures += 1
                        logger.warning(f"⚠️ Tunnel response {response.status_code}")
                else:
                    consecutive_failures += 1
                    logger.warning("⚠️ No hay URL de túnel disponible")
                
                # Si hay muchos fallos, forzar restart
                if consecutive_failures >= 5:
                    logger.error(f"💥 Túnel inaccesible ({consecutive_failures} fallos), reiniciando proceso...")
                    self._force_restart()
                    consecutive_failures = 0
                
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"⚠️ Health check falló: {e}")
            
            time.sleep(30)  # Check cada 30 segundos
    
    def _force_restart(self):
        """Fuerza el reinicio del proceso del túnel"""
        try:
            if self.process and self.process.poll() is None:
                logger.info("🔪 Terminando proceso cloudflared...")
                self.process.terminate()
                time.sleep(5)
                if self.process.poll() is None:
                    self.process.kill()
            self.current_url = None
        except Exception as e:
            logger.error(f"Error forzando restart: {e}")
    
    def _update_secrets_file(self, url):
        """Actualiza archivo de secretos con nueva URL"""
        try:
            data = {'cloudflare': {'url': url}}
            secrets_path = os.path.join(os.path.dirname(__file__), 'secrets_tunnel.toml')
            with open(secrets_path, 'w') as f:
                toml.dump(data, f)
            logger.info(f"📝 Archivo secrets_tunnel.toml actualizado")
        except Exception as e:
            logger.error(f"Error actualizando secrets: {e}")
    
    def get_current_url(self):
        """Obtiene la URL actual del túnel"""
        return self.current_url
    
    def stop(self):
        """Detiene el manager del túnel"""
        self.monitoring = False
        self._force_restart()
        logger.info("🛑 Cloudflare Tunnel Manager detenido")
```

### **SOLUCIÓN 4: Sincronización de Estado Robusta**

```python
# ✅ SOLUCIÓN: Estado de dispositivos con heartbeat
class DeviceStateManager:
    def __init__(self, db_client):
        self.db_client = db_client
        self.device_states = {}
        self.heartbeat_interval = 60  # 1 minuto
        self.offline_threshold = 300  # 5 minutos
        self.start_heartbeat_monitor()
    
    def start_heartbeat_monitor(self):
        """Inicia monitor de heartbeat para dispositivos"""
        def heartbeat_loop():
            while True:
                try:
                    self._update_device_states()
                    self._check_offline_devices()
                    self._cleanup_stale_data()
                except Exception as e:
                    logger.error(f"Error en heartbeat monitor: {e}")
                time.sleep(self.heartbeat_interval)
        
        thread = threading.Thread(target=heartbeat_loop, daemon=True)
        thread.start()
        logger.info("💓 Device heartbeat monitor iniciado")
    
    def _update_device_states(self):
        """Actualiza estados de dispositivos basado en datos recientes"""
        try:
            # Obtener datos de los últimos 5 minutos
            recent_data = self.db_client.execute_with_retry("""
                SELECT device_id, MAX(timestamp) as last_data, COUNT(*) as data_count
                FROM sensor_data 
                WHERE timestamp >= NOW() - INTERVAL '5 minutes'
                GROUP BY device_id
            """)
            
            now = datetime.now(timezone.utc)
            
            for record in recent_data:
                device_id = record['device_id']
                last_data = record['last_data']
                data_count = record['data_count']
                
                # Calcular tiempo desde último dato
                if isinstance(last_data, str):
                    last_dt = datetime.fromisoformat(last_data.replace('Z', '+00:00'))
                else:
                    last_dt = last_data.replace(tzinfo=timezone.utc)
                
                time_since_last = (now - last_dt).total_seconds()
                
                # Determinar estado
                if time_since_last <= self.offline_threshold:
                    new_status = 'online'
                    health_score = min(100, (data_count / 5) * 100)  # 5 datos esperados en 5 min
                else:
                    new_status = 'offline'
                    health_score = 0
                
                # Actualizar estado si cambió
                if self.device_states.get(device_id, {}).get('status') != new_status:
                    self._update_device_status(device_id, new_status, {
                        'last_data_time': last_dt.isoformat(),
                        'health_score': health_score,
                        'data_points_5min': data_count
                    })
                    
                self.device_states[device_id] = {
                    'status': new_status,
                    'last_update': now.isoformat(),
                    'health_score': health_score
                }
                    
        except Exception as e:
            logger.error(f"Error actualizando estados de dispositivos: {e}")
    
    def _update_device_status(self, device_id, status, metadata=None):
        """Actualiza estado de dispositivo en BD"""
        try:
            self.db_client.execute_with_retry("""
                UPDATE devices 
                SET status = %s, last_seen = NOW(), metadata = COALESCE(%s::jsonb, metadata)
                WHERE device_id = %s
            """, (status, json.dumps(metadata) if metadata else None, device_id))
            
            # Log del cambio de estado
            self.db_client.execute_with_retry("""
                INSERT INTO system_events (event_type, device_id, message, metadata)
                VALUES (%s, %s, %s, %s)
            """, ('device_status_change', device_id, f'Estado cambiado a {status}', json.dumps(metadata)))
            
            logger.info(f"📱 {device_id}: {status} (health: {metadata.get('health_score', 0)}%)")
            
        except Exception as e:
            logger.error(f"Error actualizando estado de {device_id}: {e}")

# ✅ IMPLEMENTACIÓN: API endpoint mejorado con estado consistente
@app.get("/devices/status")
async def get_devices_with_realtime_status():
    """Endpoint optimizado que devuelve estado en tiempo real"""
    try:
        # Consulta optimizada que une devices con datos recientes
        devices_with_status = db_client.execute_with_retry("""
            SELECT 
                d.*,
                COALESCE(recent.last_data, d.last_seen) as actual_last_seen,
                COALESCE(recent.data_count, 0) as recent_data_count,
                CASE 
                    WHEN recent.last_data >= NOW() - INTERVAL '5 minutes' THEN 'online'
                    WHEN recent.last_data >= NOW() - INTERVAL '30 minutes' THEN 'idle'
                    ELSE 'offline'
                END as computed_status
            FROM devices d
            LEFT JOIN (
                SELECT 
                    device_id,
                    MAX(timestamp) as last_data,
                    COUNT(*) as data_count
                FROM sensor_data 
                WHERE timestamp >= NOW() - INTERVAL '30 minutes'
                GROUP BY device_id
            ) recent ON d.device_id = recent.device_id
            WHERE d.device_type IN ('arduino_ethernet', 'esp32_wifi', 'arduino_usb')
            ORDER BY recent.last_data DESC NULLS LAST
        """)
        
        return {
            "success": True,
            "data": devices_with_status,
            "timestamp": datetime.now().isoformat(),
            "total_devices": len(devices_with_status),
            "online_devices": len([d for d in devices_with_status if d['computed_status'] == 'online'])
        }
        
    except Exception as e:
        logger.error(f"Error en get_devices_with_realtime_status: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estado de dispositivos")
```

---

## 🎯 Plan de Implementación Prioritario (Backend Jetson Nano)

### **FASE 1: Estabilización Inmediata (1-2 días) - ESTADO: 🔄 EN PROGRESO**

#### ✅ **1.1 Implementar cache interno en API FastAPI (Jetson Nano)** - ✅ COMPLETADO
- [x] Cache en memoria para datos frecuentes (`APIInternalCache`) - **✅ IMPLEMENTADO Y VALIDADO**
- [x] Fallback a datos persistentes en `/tmp/iot_api_fallback.json` - **✅ IMPLEMENTADO Y VALIDADO**
- [x] Respuestas siempre válidas para Streamlit Cloud (nunca retornar `None`) - **✅ IMPLEMENTADO Y VALIDADO**
- [x] **Prueba**: Verificar que API responde consistentemente durante fallo de PostgreSQL - **✅ VALIDADO**
- [x] **Prueba**: Confirmar que cache se persiste y recupera correctamente - **✅ VALIDADO**

**📁 Archivos implementados:**
- `backend/api_cache.py` - Sistema de cache completo (214 líneas)
- `backend/api.py` - Actualizado con integración de cache en todos los endpoints críticos
- `test_phase1_simple.py` - Script de validación exitoso
- Endpoints resilientes: `/health`, `/devices`, `/data/{device_id}`, `/data`, `/scan/network`, `/acquisition/*`

**🧪 Validación completada:**
- ✅ Cache en memoria con TTL configurable
- ✅ Persistencia automática en disco
- ✅ Respuestas resilientes (nunca HTTP 500)
- ✅ Thread safety para Jetson Nano
- ✅ Auto-cleanup de entradas expiradas

#### ✅ **1.2 Mejorar manejo de errores PostgreSQL** - ✅ COMPLETADO
- [x] Aumentar timeouts de conexión de 3s a 15s en `db_writer.py` - **✅ IMPLEMENTADO Y VALIDADO**
- [x] Implementar retry automático (3 intentos) en queries críticas - **✅ IMPLEMENTADO Y VALIDADO**
- [x] Logging detallado de errores de conexión con contexto - **✅ IMPLEMENTADO Y VALIDADO**
- [x] **Prueba**: Simular desconexión de PostgreSQL y verificar recovery - **✅ VALIDADO**
- [x] **Prueba**: Confirmar que logs muestran información útil para debugging - **✅ VALIDADO**

**📁 Archivos implementados:**
- `backend/db_writer.py` - Completamente reescrito con manejo robusto (605 líneas)
- `test_phase1_postgresql_simple.py` - Script de validación exitoso
- Métodos mejorados: `_connect_with_retry()`, `_ensure_connection()`, `_execute_with_retry()`

**🔧 Mejoras técnicas implementadas:**
- ✅ Timeouts: conexión 15s, queries 30s (optimizado para Jetson Nano)
- ✅ Reintentos: 3 intentos con backoff exponencial (2s, 4s, 8s)
- ✅ Autocommit habilitado para operaciones simples
- ✅ Verificación proactiva de conexiones (`SELECT 1`)
- ✅ Manejo diferenciado: OperationalError (retry) vs DatabaseError (no retry)
- ✅ Logging con iconos y contexto detallado

#### ✅ **1.3 Actualizar servicio Cloudflare Tunnel**
- [ ] Health check cada 45 segundos (optimizado para Jetson)
- [ ] Auto-restart con backoff exponencial (10s, 20s, 40s, 60s, 120s max)
- [ ] Notificación a API cuando URL cambia (`/internal/tunnel_url_update`)
- [ ] **Prueba**: Forzar caída del túnel y verificar auto-recovery < 2 minutos
- [ ] **Prueba**: Confirmar que nueva URL se propaga correctamente a `/cf_url`

**🔧 Comandos de implementación Fase 1:**
```bash
# En Jetson Nano - Preparación:
sudo systemctl stop acquire_data.service start_cloudflare_py.service

# Backup de archivos originales:
cp backend/api.py backend/api.py.backup
cp backend/db_writer.py backend/db_writer.py.backup  
cp start_cloudflare.py start_cloudflare.py.backup

# Implementar código (se realizará paso a paso)
# Reiniciar servicios con nuevas configuraciones:
sudo systemctl daemon-reload
sudo systemctl start iot-backend-api.service iot-tunnel.service
```

#### 🧪 **Pruebas de Validación Fase 1:**
1. **Test de Resilencia de Cache**:
   ```bash
   # Desconectar PostgreSQL temporalmente
   sudo systemctl stop postgresql
   # Verificar que API sigue respondiendo con datos cached
   curl http://localhost:8000/data/esp32_wifi_001
   # Reconectar PostgreSQL  
   sudo systemctl start postgresql
   ```

2. **Test de Auto-Recovery del Túnel**:
   ```bash
   # Forzar terminación del proceso cloudflared
   sudo pkill -f cloudflared
   # Verificar que se reinicia automáticamente en < 2 minutos
   # Confirmar nueva URL en secrets_tunnel.toml
   ```

3. **Test de Carga desde Streamlit Cloud**:
   ```bash
   # Simular múltiples requests concurrentes
   for i in {1..10}; do
     curl -s http://localhost:8000/data &
   done
   # Verificar que todas las respuestas son válidas (no 500 errors)
   ```

### **FASE 2: Robustez Estructural (3-5 días) - ESTADO: ⏳ PENDIENTE**

#### ✅ **2.1 Implementar connection pooling PostgreSQL en Jetson Nano**
- [ ] Pool de 1-5 conexiones (optimizado para recursos limitados)
- [ ] Auto-recovery de conexiones perdidas con backoff exponencial
- [ ] Health monitor cada 60 segundos para el pool
- [ ] **Prueba**: Saturar pool con conexiones y verificar manejo elegante
- [ ] **Prueba**: Simular reinicio de PostgreSQL y confirmar recovery automático

#### ✅ **2.2 Restructurar servicios systemd con dependencias**
- [ ] Crear `iot-postgresql.service` → `iot-backend-api.service` → `iot-tunnel.service`
- [ ] Health checks automáticos entre servicios con timeouts apropiados
- [ ] Restart coordinado en caso de fallo (restart en cascada si es necesario)
- [ ] **Prueba**: Reiniciar PostgreSQL y verificar que servicios dependientes se recuperan
- [ ] **Prueba**: Verificar orden de inicio correcto en boot del sistema

#### ✅ **2.3 Optimizar consultas PostgreSQL para Jetson Nano**
- [ ] Añadir índices adicionales en `sensor_data(device_id, timestamp)`
- [ ] Queries con LIMIT optimizado para recursos limitados  
- [ ] Cleanup automático de datos > 30 días (job semanal)
- [ ] **Prueba**: Benchmark de queries antes/después de optimización
- [ ] **Prueba**: Verificar que cleanup automático funciona sin afectar performance

### **FASE 3: Optimización Avanzada (1 semana) - ESTADO: ⏳ PENDIENTE**

#### ✅ **3.1 Monitoreo y alertas en Jetson Nano**  
- [ ] Dashboard local de métricas del sistema (`/admin/metrics`)
- [ ] Alertas por logs cuando servicios fallan (syslog integration)
- [ ] Scripts de auto-diagnóstico (`jetson_health_check.py`)
- [ ] **Prueba**: Simular fallos y verificar que alertas se generan correctamente
- [ ] **Prueba**: Confirmar que dashboard muestra métricas en tiempo real

#### ✅ **3.2 Backup automático y recovery**
- [ ] pg_dump diario automatizado (cron job a las 2:00 AM)
- [ ] Scripts de restauración rápida (`restore_from_backup.sh`)  
- [ ] Backup de configuraciones críticas (`secrets_tunnel.toml`, services)
- [ ] **Prueba**: Ejecutar proceso completo de backup y restore
- [ ] **Prueba**: Verificar que backups funcionan en disco lleno

#### ✅ **3.3 Performance tuning para Jetson Nano**
- [ ] Configuración PostgreSQL optimizada para ARM (`postgresql.conf`)
- [ ] Gestión de memoria para evitar swapping (`vm.swappiness=10`)
- [ ] Monitoreo de temperatura y throttling automático
- [ ] **Prueba**: Stress test del sistema completo durante 24 horas
- [ ] **Prueba**: Verificar que sistema mantiene performance bajo carga térmica

**🔧 Configuración de monitoreo:**
```bash
# Script de monitoreo continuo en Jetson Nano
# Verificar CPU, memoria, temperatura, servicios
# Generar alertas automáticas en logs
```

---

## 📊 Métricas de Éxito (Enfoque Backend)

### **Objetivos Cuantificables para Jetson Nano:**

- **Uptime de servicios systemd**: > 99.5% (menos de 36 minutos de downtime por mes)
- **Tiempo de respuesta de API local**: < 1 segundo en el 95% de requests
- **Recovery time de servicios**: < 30 segundos después de una falla
- **Estabilidad de túnel Cloudflare**: > 99% uptime, reconexión automática < 60s

### **Indicadores de Estabilidad Backend:**

```python
# ✅ Métricas implementables en Jetson Nano
jetson_metrics = {
    'api_response_time_p95': 1.0,  # segundos (local)
    'database_connection_success_rate': 0.995,  # 99.5%
    'tunnel_uptime_percentage': 0.99,  # 99%
    'systemd_service_restart_rate': 0.01,  # 1% máximo reinicio diario
    'memory_usage_max': 0.8,  # 80% máximo uso de RAM
    'cpu_temp_max': 70,  # 70°C máximo para evitar throttling
    'recovery_time_seconds': 30  # tiempo máximo de recuperación
}
```

---

## 💡 Recomendaciones Específicas para Jetson Nano

### **Optimizaciones Hardware:**

1. **Gestión Térmica**
   - Monitoreo de temperatura de CPU/GPU
   - Throttling automático para prevenir sobrecalentamiento
   - Fan control inteligente si está disponible

2. **Gestión de Memoria**
   - Configurar swap mínimo para evitar degradación de SD
   - Tuning de PostgreSQL para 4GB RAM
   - Cache sizing apropiado para recursos limitados

3. **Almacenamiento**
   - SD card de alta velocidad (Class 10 mínimo)
   - Logs rotativos para evitar llenar almacenamiento
   - Backup regular de configuraciones

### **Configuraciones PostgreSQL para Jetson Nano:**

```sql
-- ✅ Configuración optimizada postgresql.conf
shared_buffers = 256MB          # 1/4 de RAM disponible
effective_cache_size = 1GB      # Estimación de cache OS
work_mem = 4MB                  # Por conexión
maintenance_work_mem = 64MB     # Para VACUUM, CREATE INDEX
max_connections = 20            # Límite conservador
wal_buffers = 16MB             # WAL buffer size
checkpoint_segments = 8         # Checkpoint frequency  
```

### **Monitoreo de Recursos:**

```python
# ✅ Script de monitoreo para Jetson Nano
import psutil
import subprocess

def check_jetson_health():
    """Monitor específico para Jetson Nano"""
    health = {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'temperature': get_jetson_temp(),
        'services_status': check_systemd_services(),
        'tunnel_connectivity': test_tunnel_health()
    }
    
    # Alertas automáticas
    if health['cpu_percent'] > 80:
        logger.warning(f"🔥 CPU alta: {health['cpu_percent']}%")
    if health['memory_percent'] > 85:
        logger.warning(f"🧠 Memoria alta: {health['memory_percent']}%")
    if health['temperature'] > 70:
        logger.critical(f"🌡️ Temperatura crítica: {health['temperature']}°C")
    
    return health
```

---

## 🚀 Conclusión Actualizada

El sistema IoT puede alcanzar estabilidad del **99.5%** implementando todas las soluciones **en el backend de la Jetson Nano**, considerando las limitaciones de Streamlit Cloud. La estrategia se enfoca en:

### **Principios Clave:**
1. **Cache interno en API** - Streamlit Cloud siempre recibe respuestas válidas
2. **Auto-recovery automático** - Servicios se recuperan sin intervención manual  
3. **Coordinación de servicios** - systemd dependencies aseguran inicio ordenado
4. **Monitoreo proactivo** - Detección temprana de problemas en Jetson

### **Arquitectura Final Estable:**
```
[Streamlit Cloud] 
    ↓ HTTPS requests (timeout: 15s)
[Cloudflare Tunnel] ← Auto-recovery, health checks
    ↓ Local HTTP
[FastAPI + Cache] ← Connection pooling, fallback data
    ↓ Connection pool
[PostgreSQL] ← Optimized for Jetson Nano
    ↑ Data insertion
[Data Acquisition] ← Robust device reconciliation
```

### **Próximos Pasos Inmediatos:**

1. ✅ Implementar `APIInternalCache` en FastAPI (Jetson Nano)
2. ✅ Configurar connection pooling PostgreSQL optimizado
3. ✅ Crear servicios systemd coordinados con dependencias
4. ✅ Implementar health monitoring de túnel Cloudflare
5. ✅ Establecer métricas de monitoreo automático

**Este enfoque garantiza estabilidad del sistema sin depender de capacidades limitadas de Streamlit Cloud, concentrando toda la robustez en el backend de la Jetson Nano.**