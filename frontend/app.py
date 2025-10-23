"""
Dashboard principal de Streamlit para el sistema IoT
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import time
from streamlit_autorefresh import st_autorefresh


# Configuración de página
st_autorefresh(interval=30 * 1000, key="data_refresh")
st.set_page_config(
    page_title="IoT Dashboard",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Banner de estado de desarrollo
st.markdown(
    '''
    <div style="background-color:#fff3cd; border-left:6px solid #ff9800; padding:1em; margin-bottom:1em; display:flex; align-items:center;">
        <span style="font-size:2em; margin-right:0.5em;">🚧</span>
        <span style="font-size:1.2em; color:#856404;">
            <b>¡Atención!</b> Esta aplicación aún se encuentra <b>en desarrollo</b>.
        </span>
    </div>
    ''',
    unsafe_allow_html=True
)

# CSS personalizado
st.markdown("""
<style>
.metric-container {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 4px solid #1f77b4;
}

.status-online { color: #28a745; }
.status-offline { color: #dc3545; }
.status-error { color: #ffc107; }

.device-card {
    background: white;
    padding: 1rem;
    border-radius: 0.5rem;
    border: 1px solid #ddd;
    margin: 0.5rem 0;
}

.sidebar-content {
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 0.5rem;
}
</style>
""", unsafe_allow_html=True)





# --- Detección automática y robusta de la URL pública de Cloudflare Tunnel ---
st.sidebar.markdown("### 🌐 URL de la API Jetson (Cloudflare Tunnel)")
st.sidebar.markdown("---")
st.sidebar.markdown("#### 🔗 Configuración de URL pública de la API")


# --- Sistema robusto de detección de URL de Cloudflare Tunnel ---
import time
from urllib.parse import urlparse

# URLs conocidas ordenadas por prioridad (las más recientes primero)
KNOWN_CF_URLS = [
    "https://trained-clean-sin-brian.trycloudflare.com",  # URL actual Oct 23, 2025 - 08:26 (auto-sync)
    "https://flags-northern-anytime-filed.trycloudflare.com",  # URL actual Oct 23, 2025 - 07:45 (auto-sync)
    "https://ancient-expect-consistently-adapted.trycloudflare.com",  # URL actual Oct 23, 2025 - 02:46 (auto-sync)
    "https://financial-road-frequently-les.trycloudflare.com",  # URL actual Oct 23, 2025 - 02:32 (auto-sync)
    "https://photographers-theories-cricket-corporations.trycloudflare.com",  # URL actual Oct 23, 2025 - 01:52 (auto-sync)
    "https://returned-convenience-tower-switched.trycloudflare.com",  # URL actual Oct 23, 2025 - 01:01 (auto-sync)
    "https://reflect-wed-governmental-fisher.trycloudflare.com",  # URL actual Oct 23, 2025 - 00:13 (auto-sync)
    "https://parade-species-club-represented.trycloudflare.com",  # URL actual Oct 22, 2025 - 23:51 (auto-sync)
    "https://coverage-grams-bra-atlantic.trycloudflare.com",  # URL actual Oct 22, 2025 - 22:54 (auto-sync)
    "https://replica-subscriber-permission-restricted.trycloudflare.com",  # URL actual Oct 22, 2025 - 15:11 (auto-sync)
    "https://strike-ball-belts-lawsuit.trycloudflare.com",  # URL actual Oct 22, 2025 - 14:39 (auto-sync)
    "https://sherman-affiliated-kai-eugene.trycloudflare.com",  # URL actual Oct 22, 2025 - 13:13 (auto-sync)
    "https://trunk-lynn-possibility-radio.trycloudflare.com",  # URL actual Oct 22, 2025 - 13:06 (auto-sync)
    "https://test-auto-sync-demo-url.trycloudflare.com",  # URL actual Oct 22, 2025 - 13:03 (auto-sync)
    "https://trunk-lynn-possibility-radio.trycloudflare.com",
    "https://conventional-packaging-sheffield-cycles.trycloudflare.com",
    "https://plain-state-refers-nutritional.trycloudflare.com",
    "https://wheel-wind-scanning-indicate.trycloudflare.com",  # URL actual Oct 21, 2025 - 18:09 (reinicio completo servicios)
    "https://liquid-streaming-welding-something.trycloudflare.com",  # URL anterior Oct 21, 2025 - 19:57 (migración a Arch server)
    "https://wonder-sufficiently-generator-click.trycloudflare.com",
    "https://respect-craps-lit-aged.trycloudflare.com",
    "https://exchange-ace-inclusive-attraction.trycloudflare.com",
    "https://nodes-avi-twelve-confident.trycloudflare.com",
    "https://continent-logged-faqs-vernon.trycloudflare.com",
    "https://stats-intervals-individuals-film.trycloudflare.com",
    "https://atomic-suggested-albums-pushing.trycloudflare.com",
    "https://dependent-discussions-venice-filling.trycloudflare.com",
    "https://pins-customized-coastal-scope.trycloudflare.com",
    "https://sixth-casey-weblogs-acne.trycloudflare.com",  # URL anterior Oct 10, 2025 - 08:19 (post-crasheo resiliente)
    "https://hotels-size-imposed-alpine.trycloudflare.com",  # URL anterior Oct 9, 2025 - 22:45 (servicio resiliente)
    "https://warm-procedures-rick-rotary.trycloudflare.com",  # URL anterior Oct 9, 2025 - 22:40 (test manual)
    "https://adventure-extreme-adjust-clicking.trycloudflare.com",  # URL anterior Oct 9, 2025 - 22:32
    "https://wake-fascinating-exploration-fuel.trycloudflare.com",  # URL anterior Oct 9, 2025 - 21:20 
    "https://cabinets-extraction-affairs-plant.trycloudflare.com",  # URL anterior Oct 9, 2025 - 18:34 
    "https://coated-clark-separated-bill.trycloudflare.com",  # URL anterior Oct 9, 2025 - 18:13 
    "https://licensed-again-players-debate.trycloudflare.com",  # URL anterior Oct 9, 2025 - 17:52 
    "https://flash-words-knife-joining.trycloudflare.com",  # URL anterior Oct 9, 2025 - 17:18
    "https://worthy-votes-mph-principles.trycloudflare.com"  # URL anterior Oct 9, 2025 - 16:20
]

def handle_api_error(e, operation="API call", show_error=True):
    """Maneja errores de API de manera consistente y user-friendly"""
    error_msg = "Conexión con el Jetson Nano perdida"
    
    if hasattr(e, 'response') and e.response is not None:
        if e.response.status_code == 404:
            error_msg = "Endpoint no encontrado en la API"
        elif e.response.status_code == 500:
            error_msg = "Error interno del servidor Jetson"
        elif e.response.status_code == 503:
            error_msg = "Servicio temporalmente no disponible"
        else:
            error_msg = f"Error HTTP {e.response.status_code}"
    elif "timeout" in str(e).lower():
        error_msg = "Timeout - El Jetson Nano no responde"
    elif "connection" in str(e).lower():
        error_msg = "No se puede conectar con el Jetson Nano"
    
    if show_error:
        st.error(f"❌ {operation}: {error_msg}")
    
    return None

def check_url_health(url, timeout=5):
    """Verifica si una URL está disponible y responde correctamente"""
    try:
        response = requests.get(f"{url}/health", timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False

def get_current_url_from_endpoint(url, timeout=8):
    """Obtiene la URL actual desde el endpoint /cf_url de una URL base"""
    try:
        response = requests.get(f"{url}/cf_url", timeout=timeout)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') and data.get('cf_url'):
                return data['cf_url']
    except Exception:
        pass
    return None

@st.cache_data(ttl=60)  # Cache por 1 minuto para reducir requests
def get_public_cf_url():
    """
    Sistema robusto de detección de URL con múltiples estrategias:
    1. Intenta obtener URL actual desde endpoints /cf_url conocidos
    2. Verifica salud de URLs detectadas
    3. Usa URLs conocidas como fallback
    4. Implementa timeouts y reintentos apropiados
    """
    
    # Estrategia 1: Intentar obtener URL actual desde endpoints conocidos
    for base_url in KNOWN_CF_URLS:
        current_url = get_current_url_from_endpoint(base_url, timeout=6)
        if current_url:
            # Verificar que la URL detectada funcione
            if check_url_health(current_url, timeout=5):
                if current_url != base_url:
                    st.sidebar.success(f"🔄 URL actualizada automáticamente: {current_url}")
                return current_url
            else:
                st.sidebar.warning(f"⚠️ URL detectada {current_url} no responde, probando alternativas...")
    
    # Estrategia 2: Verificar URLs conocidas directamente
    st.sidebar.info("🔍 Verificando URLs conocidas...")
    for url in KNOWN_CF_URLS:
        if check_url_health(url, timeout=4):
            st.sidebar.info(f"✅ URL funcional encontrada: {url}")
            return url
    
    # Estrategia 3: Último recurso - usar la primera URL conocida con advertencia
    fallback_url = KNOWN_CF_URLS[0]
    st.sidebar.error(f"❌ No se encontró ninguna URL funcional. Usando {fallback_url} como fallback.")
    st.sidebar.error("🔧 Si persiste el problema, contacta al administrador del sistema.")
    return fallback_url



# Siempre intenta descubrir la URL pública automáticamente y actualizar si cambia
if 'api_url' not in st.session_state:
    st.session_state['api_url'] = None
if 'url_last_check' not in st.session_state:
    st.session_state['url_last_check'] = 0
if 'connectivity_status' not in st.session_state:
    st.session_state['connectivity_status'] = "unknown"

# Verificar URL cada 2 minutos o si no hay URL configurada
current_time = time.time()
should_check_url = (
    not st.session_state['api_url'] or 
    (current_time - st.session_state['url_last_check']) > 120
)

if should_check_url:
    st.session_state['url_last_check'] = current_time
    auto_url = get_public_cf_url()
    
    if auto_url:
        # Verificar conectividad actual
        if check_url_health(auto_url, timeout=3):
            st.session_state['connectivity_status'] = "connected"
            if auto_url != st.session_state['api_url']:
                st.session_state['api_url'] = auto_url
                st.sidebar.success(f"🌐 URL pública detectada: {auto_url}")
        else:
            st.session_state['connectivity_status'] = "failed"
            st.sidebar.error("❌ No se puede conectar con la API del Jetson")
    else:
        st.session_state['connectivity_status'] = "no_url"
        st.sidebar.error("🔍 No se pudo detectar ninguna URL válida")

# Mostrar estado de conectividad en la sidebar
if st.session_state['api_url']:
    if st.session_state['connectivity_status'] == "connected":
        st.sidebar.success(f"✅ API conectada: {st.session_state['api_url']}")
    elif st.session_state['connectivity_status'] == "failed":
        st.sidebar.error(f"❌ API no responde: {st.session_state['api_url']}")
        st.sidebar.info("🔄 La app intentará reconectar automáticamente")
    else:
        st.sidebar.warning(f"⚠️ Verificando conectividad: {st.session_state['api_url']}")
else:
    st.sidebar.error("❌ Sin conexión a la API del Jetson Nano")
    st.sidebar.info("🔧 Verifique que los servicios estén ejecutándose")

API_URL = st.session_state['api_url']

class IoTDashboard:
    """Dashboard que consulta datos directamente de la API Jetson (FastAPI)"""
    def __init__(self):
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        if 'selected_device' not in st.session_state:
            st.session_state.selected_device = None

        # Enviar ping asíncrono al backend para dejar evidencia en logs/DB
        try:
            if API_URL:
                def ping_backend():
                    try:
                        headers = {'Content-Type': 'application/json'}
                        payload = {
                            'origin': API_URL,
                            'user_agent': 'streamlit-frontend'
                        }
                        requests.post(f"{API_URL}/debug/frontend_ping", json=payload, timeout=5)
                    except Exception:
                        pass
                # No bloquear: lanzar en hilo
                import threading
                t = threading.Thread(target=ping_backend, daemon=True)
                t.start()
        except Exception:
            pass

    def get_sensor_data_by_time_range(self, time_range=None, hours=None, days=None):
        """Obtiene los datos de sensores filtrando por rango de tiempo"""
        if not API_URL:
            st.error("❌ URL de API no configurada. Verifica la conexión con el Jetson Nano.")
            return None
        
        try:
            url = f"{API_URL}/data"
            params = {}
            
            # Configurar parámetros según el rango de tiempo
            if time_range == "real_time":
                params['hours'] = 0.17  # Aproximadamente 10 minutos (10/60 = 0.167)
            elif time_range == "hour":
                params['hours'] = 1
            elif time_range == "day": 
                params['days'] = 1
            elif time_range == "week":
                params['days'] = 7
            elif time_range == "month":
                params['days'] = 30
            elif time_range == "year":
                params['days'] = 365
            elif hours:
                params['hours'] = hours
            elif days:
                params['days'] = days
            else:
                params['limit'] = 1000  # Fallback para datos recientes
            
            # Debug: mostrar qué parámetros se están enviando
            st.write(f"🔍 **Debug API Call:** URL: {url}, Params: {params}")
            
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                result_data = data.get('data', [])
                st.write(f"✅ **API Response:** Recibidos {len(result_data)} registros")

                # Fallback automático: si la ventana en tiempo real devuelve muy pocos
                # registros, reintentar con 1 hora para poblar gráficos (UX friendly).
                try:
                    sent_hours = params.get('hours') if isinstance(params, dict) else None
                    if sent_hours is not None:
                        # si recibimos <=3 puntos en 10min, ampliar a 1h
                        if len(result_data) <= 3 and float(sent_hours) < 1.0:
                            st.write("ℹ️ Pocos registros en ventana corta, reintentando con 1 hora...")
                            params['hours'] = 1.0
                            resp2 = requests.get(url, params=params, timeout=15)
                            if resp2.status_code == 200:
                                data2 = resp2.json()
                                result_data = data2.get('data', [])
                                st.write(f"✅ **API Response (fallback 1h):** Recibidos {len(result_data)} registros")
                except Exception:
                    # No bloquear la experiencia si falla el fallback
                    pass

                return result_data
            else:
                return handle_api_error(Exception(f"HTTP {resp.status_code}: {resp.text}"), 
                                      "Consulta de datos de sensores")
        except requests.exceptions.Timeout:
            return handle_api_error(Exception("timeout"), "Consulta de datos de sensores")
        except requests.exceptions.ConnectionError:
            return handle_api_error(Exception("connection"), "Consulta de datos de sensores") 
        except Exception as e:
            return handle_api_error(e, "Consulta de datos de sensores")

    def get_sensor_data(self, limit=500):
        """Método legacy - usar get_sensor_data_by_time_range en su lugar"""
        if not API_URL:
            st.error("Debes ingresar la URL pública de la API Jetson (Cloudflare Tunnel) en la barra lateral.")
            return None
        try:
            url = f"{API_URL}/data"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('data', [])
            else:
                st.error(f"❌ Error consultando API: {resp.status_code} {resp.text}")
                return None
        except Exception as e:
            st.error(f"❌ Error consultando API: {e}")
            return None

    def get_all_devices(self):
        if not API_URL:
            st.sidebar.error("Debes ingresar la URL pública de la API Jetson (Cloudflare Tunnel)")
            return []
        try:
            # Solicitar sólo dispositivos que estén online para evitar mostrar opciones sin datos
            url = f"{API_URL}/devices"
            resp = requests.get(url, params={'only_online': True}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                devices = data.get('data', [])
                device_ids = [d['device_id'] for d in devices if 'device_id' in d and d.get('online')]
                # Mostrar en la barra lateral sólo los dispositivos online
                if device_ids:
                    st.sidebar.write(f"🔍 Dispositivos online: {len(device_ids)}")
                    for device in device_ids:
                        st.sidebar.write(f"  • {device}")
                else:
                    st.sidebar.info("No hay dispositivos online en este momento.")
                return device_ids
            else:
                st.sidebar.error(f"❌ Error obteniendo dispositivos: {resp.status_code} {resp.text}")
                return []
        except Exception as e:
            st.sidebar.error(f"❌ Error obteniendo lista de dispositivos: {e}")
            return []
    def get_service_status(self):
        """Consulta el endpoint /service_status del backend para obtener el estado de los servicios."""
        if not API_URL:
            st.error("Debes ingresar la URL pública de la API Jetson (Cloudflare Tunnel) en la barra lateral.")
            return {}
        try:
            url = f"{API_URL}/service_status"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('success') and 'services' in data:
                    return data['services']
                else:
                    st.error(f"❌ Error consultando estado de servicios: {data.get('error', 'Respuesta inválida')}")
                    return {}
            else:
                st.error(f"❌ Error consultando estado de servicios: {resp.status_code} {resp.text}")
                return {}
        except Exception as e:
            st.error(f"❌ Error consultando estado de servicios: {e}")
            return {}

    def verify_api_connection(self):
        """Verifica la conexión con la API Jetson y muestra estadísticas"""
        if not API_URL:
            st.sidebar.error("Debes ingresar la URL pública de la API Jetson (Cloudflare Tunnel)")
            return False
        try:
            url = f"{API_URL}/health"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                st.sidebar.success("✅ Conexión con API Jetson establecida")
                st.sidebar.write(f"📊 Dispositivos detectados: {data.get('devices_count', 0)}")
                return True
            else:
                st.sidebar.error(f"❌ Error de conexión con API: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            st.sidebar.error(f"❌ Error de conexión con API: {e}")
            return False

    def render_overview(self):
        st.title("🌐 IoT Dashboard - Vista General")
        st.markdown("<b>🔄 Pipeline IoT End-to-End</b>", unsafe_allow_html=True)
        try:
            with open("frontend/pipeline_iot.svg", "r") as f:
                svg_content = f.read()
            st.markdown(f'<div style="width:100%;text-align:center">{svg_content}</div>', unsafe_allow_html=True)
            st.caption("Captura → Procesa → Visualiza")
        except Exception as e:
            st.warning(f"No se pudo cargar el diagrama SVG: {e}")
        # Estado de servicios systemd
        st.markdown("## 🛠️ Estado de Servicios")
        status_dict = self.get_service_status()
        if not status_dict:
            st.warning("No se pudo obtener el estado de los servicios o el endpoint no está disponible.")
        else:
            cols = st.columns(len(status_dict))
            for i, (label, info) in enumerate(status_dict.items()):
                emoji, color_name, color_hex = info['semaforo']
                status_text = info['status']
                cols[i].markdown(f"""
                    <div style='background:{color_hex};padding:0.5rem;border-radius:0.5rem;text-align:center;color:white;display:flex;flex-direction:column;align-items:center;'>
                        <span style='font-size:2em;'>{emoji}</span>
                        <b>{label}</b><br>
                        <span style='font-size:1.1em;'>{color_name}</span>
                        <span style='font-size:0.9em;'>{status_text}</span>
                    </div>
                """, unsafe_allow_html=True)
        # Verificar conexión con API Jetson
        if not self.verify_api_connection():
            st.error("No se puede conectar con la API Jetson. Verifique la URL pública de Cloudflare Tunnel.")
            return
        
        # Selección de dispositivo PRIMERO
        st.markdown("### 📱 Selecciona un dispositivo para visualizar sus datos")
        device_ids = self.get_all_devices()
        st.info(f"📊 Dispositivos disponibles: {len(device_ids)}")
        # Si no hay dispositivos online, evitar continuar y mostrar un mensaje claro
        if not device_ids:
            st.warning("No hay dispositivos online. Conecta un dispositivo o espera a que vuelva a estar online.")
            return
        selected_device = st.selectbox("Dispositivo:", device_ids, key="device_selector")

        # --- Filtro de rango temporal DESACTIVADO (causa problemas de rendimiento en Streamlit Cloud) ---
        # st.markdown("### ⏳ Filtro de rango temporal")
        # rango_opciones = [
        #     "Tiempo real (últimos 10 min)",
        #     "Hoy",
        #     "Semana",
        #     "Mes",
        #     "Año",
        #     "Personalizado"
        # ]
        # rango_seleccionado = st.selectbox("Selecciona el rango de tiempo a visualizar:", rango_opciones, key="rango_temporal")
        
        # --- Mapeo de selección comentado ---
        # time_range_map = {
        #     "Tiempo real (últimos 10 min)": "real_time",
        #     "Hoy": "today", 
        #     "Semana": "week",
        #     "Mes": "month",
        #     "Año": "year"
        # }
        
                
        # --- Obtención de datos comentada (filtro temporal desactivado) ---
        # if rango_seleccionado == "Personalizado":
        #     # Para personalizado, primero obtenemos datos de una semana para obtener el rango disponible
        #     st.write("🔍 Obteniendo muestra de datos para configurar rango personalizado...")
        #     data_sample = self.get_sensor_data_by_time_range(selected_device, "week")  # Muestra de una semana
        #     if data_sample:
        #         df_sample = pd.DataFrame(data_sample)
        #         df_sample['timestamp'] = pd.to_datetime(df_sample['timestamp'])
        #         min_fecha = df_sample['timestamp'].min()
        #         max_fecha = df_sample['timestamp'].max()
        #         
        #         st.write(f"📊 Datos disponibles desde {min_fecha} hasta {max_fecha}")
        #         
        #         rango_slider = st.slider(
        #             "Selecciona el rango de fechas:",
        #             min_value=min_fecha,
        #             max_value=max_fecha,
        #             value=(min_fecha, max_fecha),
        #             format="YYYY-MM-DD HH:mm"
        #         )
        #         
        #         # Para el rango personalizado, calcular horas desde ahora hacia atrás
        #         ahora = datetime.now()
        #         delta_desde_ahora = ahora - rango_slider[0]
        #         hours_range = delta_desde_ahora.total_seconds() / 3600
        #         
        #         st.write(f"🕐 Solicitando datos de las últimas {hours_range:.1f} horas")
        #         data = self.get_sensor_data_by_time_range(selected_device, hours=hours_range)
        #     else:
        #         st.error("No hay datos disponibles para configurar rango personalizado")
        #         return
        # else:
        #     # Usar mapeo directo para otros rangos
        #     time_range = time_range_map.get(rango_seleccionado, "real_time")
        #     st.write(f"🕐 Cargando datos para: {rango_seleccionado}")
        #     data = self.get_sensor_data_by_time_range(selected_device, time_range)
        
        # --- Solo cargar datos recientes (últimos 10 min) para evitar sobrecarga ---
        st.write("🕐 Cargando datos recientes (últimos 10 min)")
        data = self.get_sensor_data_by_time_range(time_range="real_time")
        
        if not data:
            st.error(f"No se pueden cargar los datos desde la API Jetson para el dispositivo {selected_device}")
            return
            
        # Filtrar datos por dispositivo seleccionado
        device_data = [record for record in data if record.get('device_id') == selected_device]
        
        if not device_data:
            st.info(f"No hay datos disponibles para {selected_device} en los últimos 10 minutos.")
            return
            
        df_device = pd.DataFrame(device_data)
        if 'raw_data' in df_device.columns:
            df_device['raw_data'] = df_device['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))

        # Mostrar información del dispositivo
        device_type = "� ESP32 WiFi" if "esp32" in selected_device.lower() else "🌐 Ethernet" if "ethernet" in selected_device.lower() else "🔗 Red" if "net_device" in selected_device.lower() else "❓ Desconocido"
        st.write(f"{device_type} **{selected_device}** - {len(df_device)} registros (últimos 10 min)")

        # Mostrar tabla principal filtrada
        st.markdown(f"### Datos de sensores - {selected_device} (últimos 10 min)")
        st.dataframe(df_device, use_container_width=True)

        # Métricas rápidas
        st.markdown("### 📊 Métricas rápidas")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total registros", len(df_device))
        with col2:
            if not df_device.empty:
                st.metric("Última actualización", str(df_device['timestamp'].max()))
            else:
                st.metric("Última actualización", "Sin datos")

        # Aplicar filtro temporal local - DESACTIVADO (solo datos recientes)
        df_device['timestamp'] = pd.to_datetime(df_device['timestamp'])
        # if rango_seleccionado == "Personalizado" and 'rango_slider' in locals():
        #     df_device_filtrado = df_device[(df_device['timestamp'] >= rango_slider[0]) & (df_device['timestamp'] <= rango_slider[1])]
        # else:
        #     # Para otros rangos, los datos ya vienen filtrados de la API
        #     df_device_filtrado = df_device.copy()
        
        # Solo usar los datos ya filtrados de la API (últimos 10 min)
        df_device_filtrado = df_device.copy()

        # Visualización de variables mejorada
        st.markdown("### 📈 Gráficos de variables")
        
        # Debug: Mostrar información sobre los datos
        st.write(f"🔍 **Debug Info:**")
        st.write(f"- DataFrame filtrado shape: {df_device_filtrado.shape}")
        st.write(f"- Columnas disponibles: {list(df_device_filtrado.columns) if not df_device_filtrado.empty else 'No data'}")
        
        if not df_device_filtrado.empty:
            st.write(f"- Tipos de sensores únicos: {df_device_filtrado['sensor_type'].unique().tolist() if 'sensor_type' in df_device_filtrado.columns else 'No sensor_type column'}")
            st.write(f"- Rango de valores: {df_device_filtrado['value'].min() if 'value' in df_device_filtrado.columns else 'No value column'} - {df_device_filtrado['value'].max() if 'value' in df_device_filtrado.columns else 'No value column'}")
        
        if not df_device_filtrado.empty and 'sensor_type' in df_device_filtrado.columns and 'value' in df_device_filtrado.columns:
            sensor_types = df_device_filtrado['sensor_type'].unique().tolist()
            st.write(f"📊 Procesando {len(sensor_types)} tipos de sensores: {sensor_types}")
            
            for sensor in sensor_types:
                st.markdown(f"#### 📈 Gráfico: {sensor}")
                df_sensor = df_device_filtrado[df_device_filtrado['sensor_type'] == sensor].copy()
                st.write(f"Datos para {sensor}: {len(df_sensor)} registros")
                if 'temp' in sensor.lower():
                    # Convertir valores a numéricos primero
                    df_sensor['value'] = pd.to_numeric(df_sensor['value'], errors='coerce')
                    # Clasificar registros por rango (ajustado para datos reales)
                    def temp_rango(val):
                        if pd.isna(val):
                            return 'N/A'
                        elif val <= 35:
                            return 'Bajo'
                        elif val <= 42:
                            return 'Medio'
                        else:
                            return 'Alto'
                    df_sensor['rango'] = df_sensor['value'].apply(temp_rango)
                    df_sensor['timestamp'] = pd.to_datetime(df_sensor['timestamp'])
                    df_sensor = df_sensor.sort_values('timestamp')
                    
                    # Colores más atractivos
                    color_map = {
                        'Bajo': '#4A90E2',     # Azul más vibrante
                        'Medio': '#F5A623',    # Naranja/Amarillo
                        'Alto': '#D0021B'      # Rojo vibrante
                    }
                    # Gráfico de área coloreada por rango
                    fig_area = go.Figure()
                    for rango in ['Bajo', 'Medio', 'Alto']:
                        df_rango = df_sensor[df_sensor['rango'] == rango]
                        if not df_rango.empty:
                            fig_area.add_trace(go.Scatter(
                                x=df_rango['timestamp'],
                                y=df_rango['value'],
                                mode='lines+markers',
                                name=rango,
                                line=dict(width=3, color=color_map[rango]),
                                fill='tonexty' if rango != 'Bajo' else 'tozeroy',
                                fillcolor=color_map[rango],
                                hovertemplate=f'{rango}: %{{y:.1f}}°C<br>%{{x}}<extra></extra>',
                                showlegend=True,
                                opacity=0.7,
                                marker=dict(size=6, color=color_map[rango])
                            ))
                    fig_area.update_layout(
                        title=f"Evolución temperatura (área coloreada por rango) - {sensor}",
                        xaxis_title="Timestamp",
                        yaxis_title="Valor de temperatura (°C)",
                        legend_title="Rango de Temperatura",
                        hovermode='x unified',
                        template='plotly_white',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(family="Arial, sans-serif", size=12),
                        title_font_size=16,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=1.02,
                            xanchor="right",
                            x=1
                        )
                    )
                    # Pie chart con colores mejorados
                    pie_counts = df_sensor['rango'].value_counts().reindex(['Bajo','Medio','Alto'], fill_value=0)
                    fig_pie = px.pie(
                        values=pie_counts.values, 
                        names=pie_counts.index, 
                        color=pie_counts.index,
                        color_discrete_map={'Bajo':'#4A90E2','Medio':'#F5A623','Alto':'#D0021B'},
                        title=f"Distribución de registros por rango de temperatura - {sensor}",
                        hole=0.3  # Hacer un donut chart más moderno
                    )
                    fig_pie.update_traces(
                        textposition='inside', 
                        textinfo='percent+label',
                        textfont_size=12,
                        marker=dict(line=dict(color='#FFFFFF', width=2))
                    )
                    # Layout de dos columnas
                    col1, col2 = st.columns([2,1])
                    with col1:
                        st.plotly_chart(fig_area, use_container_width=True)
                    with col2:
                        st.plotly_chart(fig_pie, use_container_width=True)
                elif 'ldr' in sensor.lower() or 'luz' in sensor.lower() or 'light' in sensor.lower():
                    # Gráfico de línea para LDR con estilo mejorado
                    df_sensor['value'] = pd.to_numeric(df_sensor['value'], errors='coerce')
                    df_sensor['timestamp'] = pd.to_datetime(df_sensor['timestamp'])
                    df_sensor = df_sensor.sort_values('timestamp')
                    
                    fig_ldr = go.Figure()
                    fig_ldr.add_trace(go.Scatter(
                        x=df_sensor['timestamp'],
                        y=df_sensor['value'],
                        mode='lines+markers',
                        name='Nivel de luz',
                        marker=dict(color='#FFD700', size=8, line=dict(width=2, color='#FFA500')),
                        line=dict(color='#FF8C00', width=3),
                        fill='tozeroy',
                        fillcolor='rgba(255, 215, 0, 0.3)',
                        hovertemplate='Luz: %{y}%<br>%{x}<extra></extra>'
                    ))
                    fig_ldr.update_layout(
                        title=f"Serie temporal de nivel de luz - {sensor}",
                        xaxis_title="Timestamp",
                        yaxis_title="Nivel de luz (%)",
                        template='plotly_white',
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_ldr, use_container_width=True)
                else:
                    # Gráfico de línea simple para otros sensores con estilo mejorado
                    df_sensor['value'] = pd.to_numeric(df_sensor['value'], errors='coerce')
                    df_sensor['timestamp'] = pd.to_datetime(df_sensor['timestamp'])
                    df_sensor = df_sensor.sort_values('timestamp')
                    
                    # Crear gráfico con gradiente de colores
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df_sensor['timestamp'],
                        y=df_sensor['value'],
                        mode='lines+markers',
                        name=sensor,
                        line=dict(color='#00CC96', width=3),
                        marker=dict(
                            size=8,
                            color=df_sensor['value'],
                            colorscale='Viridis',
                            showscale=True,
                            colorbar=dict(title="Valor"),
                            line=dict(width=1, color='white')
                        ),
                        fill='tozeroy',
                        fillcolor='rgba(0, 204, 150, 0.2)',
                        hovertemplate=f'{sensor}: %{{y}}<br>%{{x}}<extra></extra>'
                    ))
                    fig.update_layout(
                        title=f"Serie temporal - {sensor} ({selected_device})",
                        xaxis_title="Timestamp",
                        yaxis_title="Valor",
                        template='plotly_white',
                        showlegend=False,
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay variables numéricas para graficar.")

    def get_device_data(self, device_id, hours=24):
        """Obtener datos específicos de un dispositivo desde la API Jetson"""
        try:
            url = f"{API_URL}/data/{device_id}?hours={hours}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                return {"success": True, "data": data}
            else:
                st.error(f"❌ Error consultando datos del dispositivo {device_id}: {resp.status_code} {resp.text}")
                return {"success": False, "data": []}
        except Exception as e:
            st.error(f"❌ Error consultando datos del dispositivo {device_id}: {e}")
            return {"success": False, "data": []}

    def render_device_details(self, device_id: str):
        """Renderizar detalles de un dispositivo específico"""
        device_data = self.get_device_data(device_id, 50)
        if not device_data or not device_data.get("success"):
            st.error(f"No se pueden cargar datos del dispositivo {device_id}")
            return
        data_points = device_data.get("data", [])
        if not data_points:
            st.info(f"No hay datos históricos para {device_id}")
            return
        # Convertir a DataFrame
        df = pd.DataFrame(data_points)
        if 'raw_data' in df.columns:
            df['raw_data'] = df['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            # Gráfico temporal
            if 'sensor_data' in df.columns:
                st.markdown(f"#### 📈 Datos de {device_id}")
                try:
                    # Expandir JSON de sensor_data
                    sensor_df = pd.json_normalize(df['sensor_data'].apply(json.loads))
                    sensor_df['timestamp'] = df['timestamp'].values
                    # Crear gráfico con múltiples series
                    fig = make_subplots(
                        rows=len(sensor_df.columns) - 1,
                        cols=1,
                        shared_xaxes=True,
                        subplot_titles=[col for col in sensor_df.columns if col != 'timestamp']
                    )
                    for i, col in enumerate([c for c in sensor_df.columns if c != 'timestamp'], 1):
                        fig.add_trace(
                            go.Scatter(
                                x=sensor_df['timestamp'],
                                y=sensor_df[col],
                                name=col,
                                mode='lines+markers'
                            ),
                            row=i, col=1
                        )
                    fig.update_layout(height=400 * len([c for c in sensor_df.columns if c != 'timestamp']))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.warning(f"No se pueden visualizar los datos del sensor: {e}")
                    # Mostrar datos raw
                    st.dataframe(df, use_container_width=True)
            else:
                # Mostrar tabla de datos
                st.dataframe(df, use_container_width=True)

    def run(self):
        """Ejecutar la aplicación principal"""
        self.render_overview()
        st.markdown("---")
        st.markdown(
            "🌐 **IoT Streamlit Dashboard** | "
            f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}")

# Ejecutar aplicación
dashboard = IoTDashboard()
dashboard.run()
