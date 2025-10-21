"""
Instrucciones de instalación y configuración completa
"""

# Instalación y configuración del proyecto IoT Streamlit

## 1. Preparación del entorno

### Clonar el repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd iot_streamlit
```

### Crear entorno virtual
```bash
# Windows
python -m venv .iot_streamlit
.iot_streamlit\Scripts\activate

# Linux/macOS  
python -m venv .iot_streamlit
source .iot_streamlit/bin/activate
```

### Instalar dependencias
```bash
# Para desarrollo local (Jetson Nano)
pip install -r requirements_local.txt

# Para frontend en la nube
pip install -r requirements_cloud.txt
```

## 2. Configuración de variables de entorno

### Para desarrollo local (.env.local)
```bash
# Copiar archivo de ejemplo
cp .env.local.example .env.local

# Editar con tus credenciales
nano .env.local
```

### Para producción en la nube (.env.cloud)
```bash
cp .env.cloud.example .env.cloud
nano .env.cloud
```

## 3. Configuración de la base de datos Supabase

### Crear proyecto en Supabase
1. Ve a [supabase.com](https://supabase.com)
2. Crear nuevo proyecto
3. Obtener URL y API Key del proyecto
4. Ejecutar el schema SQL:

```sql
-- Ejecutar en el editor SQL de Supabase
-- Copiar y pegar el contenido de database/schema.sql
```

### Configurar credenciales
Añadir a tu archivo .env:
```
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu_api_key_aqui
```

## 4. Configuración de Arduino

### Arduino USB
1. Abrir `arduino/arduino_usb_sensor.ino`
2. Instalar librería ArduinoJson (Gestor de librerías)
3. Conectar sensores según diagrama
4. Subir código al Arduino
5. Anotar el puerto COM/USB usado

### Arduino Ethernet
1. Abrir `arduino/arduino_ethernet_server.ino`
2. Instalar librerías: Ethernet, ArduinoJson
3. Configurar IP estática en el código:
   ```cpp
   IPAddress ip(192, 168, 1, 100); // Cambiar según tu red
   ```
4. Cambiar MAC address si tienes múltiples dispositivos
5. Subir código al Arduino + Ethernet Shield
6. Conectar cable de red

## 5. Ejecución del sistema

### Opción 1: Sistema completo
```bash
python main.py --mode full --interval 10
```

### Opción 2: Solo API
```bash  
python main.py --mode api
```

### Opción 3: Solo adquisición de datos
```bash
python main.py --mode acquisition --interval 5
```

### Opción 4: Solo escaneo (una vez)
```bash
python main.py --mode scan
```

## 6. Verificación del sistema

### Comprobar API
```bash
# Estado del sistema
curl http://localhost:8000/status

# Lista de dispositivos
curl http://localhost:8000/devices

# Datos más recientes
curl http://localhost:8000/data
```

### Documentación de API
Abrir en navegador: http://localhost:8000/docs

## 7. Configuración del frontend Streamlit

### Desarrollo local
```bash
cd frontend
streamlit run app.py
```

### Producción en Streamlit Community Cloud
1. Subir código a GitHub
2. Conectar repositorio en [share.streamlit.io](https://share.streamlit.io)
3. Configurar secrets en Streamlit:
   ```toml
   # .streamlit/secrets.toml
   API_BASE_URL = "http://TU_IP_JETSON:8000"
   ```

## 8. Troubleshooting

### Problemas comunes

#### Arduino no detectado
```bash
# Ver puertos disponibles
python -c "import serial.tools.list_ports; print([port.device for port in serial.tools.list_ports.comports()])"
```

#### Error de conexión a Supabase
```bash
# Verificar credenciales
python -c "from backend.config import IOT_CONFIG; print(IOT_CONFIG)"
```

#### Dispositivos de red no detectados
```bash  
# Escanear red manualmente
nmap -sn 192.168.1.0/24
```

#### Puertos en uso
```bash
# Ver qué usa el puerto 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/macOS
```

### Logs del sistema
Los logs se guardan en:
- `logs/iot_system.log` (aplicación)
- Base de datos Supabase (tabla `system_events`)

### Testing de componentes

#### Test de conexión Arduino USB
```python
from backend.arduino_detector import ArduinoDetector
from backend.db_writer import SupabaseClient

db = SupabaseClient()
arduino = ArduinoDetector(db)
arduino.detect_usb_arduino()
data = arduino.read_usb_data()
print(data)
```

#### Test de escaneo de red
```python
from backend.device_scanner import DeviceScanner
from backend.db_writer import SupabaseClient

db = SupabaseClient()
scanner = DeviceScanner(db)
devices = scanner.scan_network()
print(f"Encontrados: {len(devices)} dispositivos")
```

## 9. Deployment en producción

### Jetson Nano (recomendado)
Seguir instrucciones en `README_JETSON_NANO.md`

### Docker local
```bash
# Construir imagen
docker build -t iot-backend .

# Ejecutar contenedor
docker run -d \
  --name iot-backend \
  --device=/dev/ttyUSB0 \
  -p 8000:8000 \
  -v $(pwd)/.env.local:/app/.env \
  iot-backend
```

### Raspberry Pi
Similar a Jetson Nano, pero instalar dependencias específicas:
```bash
sudo apt-get update
sudo apt-get install python3-dev python3-pip
pip install -r requirements_local.txt
```

## 10. Mantenimiento

### Backup de base de datos
Exportar desde Supabase Dashboard o usar:
```bash
pg_dump -h db.supabase.co -U postgres tu_db > backup.sql
```

### Actualizar dependencias
```bash
pip install --upgrade -r requirements_local.txt
```

### Monitoreo del sistema
- API Health: http://localhost:8000/health
- Logs sistema: http://localhost:8000/logs/system
- Dashboard Streamlit para métricas en tiempo real

¡Sistema IoT completamente funcional y listo para producción! 🚀
