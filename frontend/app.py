"""
Dashboard principal de Streamlit para el sistema IoT
"""
import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
from datetime import datetime, timedelta
import time

# Configuración de página
st.set_page_config(
    page_title="IoT Dashboard",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
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


# Configuración de Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class IoTDashboard:
    """Clase principal del dashboard"""
    
    def __init__(self):
        self.api_url = API_BASE_URL
        
        # Estado de la aplicación
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        if 'selected_device' not in st.session_state:
            st.session_state.selected_device = None
    
    def make_api_request(self, endpoint: str):
        """Realizar petición a la API con manejo de errores"""
        try:
            response = requests.get(f"{self.api_url}{endpoint}", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            st.error("❌ No se puede conectar con el backend. Verifica que esté ejecutándose.")
            return None
        except requests.exceptions.Timeout:
            st.error("⏱️ Timeout conectando con el backend")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Error de API: {e}")
            return None
    
    def get_system_status(self):
        """Obtener estado del sistema"""
        return self.make_api_request("/status")
    
    def get_devices(self):
        """Obtener lista de dispositivos"""
        return self.make_api_request("/devices")
    
    def get_latest_data(self):
        """Obtener datos más recientes"""
        return self.make_api_request("/data")
    
    def get_device_data(self, device_id: str, limit: int = 100):
        """Obtener datos de un dispositivo específico"""
        return self.make_api_request(f"/data/{device_id}?limit={limit}")
    
    def trigger_scan(self):
        """Disparar escaneo de red"""
        try:
            response = requests.post(f"{self.api_url}/scan/network", timeout=30)
            response.raise_for_status()
            return True
        except Exception as e:
            st.error(f"Error iniciando escaneo: {e}")
            return False
    
    def start_acquisition(self, interval: int = 10):
        """Iniciar adquisición continua"""
        try:
            response = requests.post(f"{self.api_url}/acquisition/start?interval={interval}")
            response.raise_for_status()
            return True
        except Exception as e:
            st.error(f"Error iniciando adquisición: {e}")
            return False
    
    def stop_acquisition(self):
        """Detener adquisición continua"""
        try:
            response = requests.post(f"{self.api_url}/acquisition/stop")
            response.raise_for_status()
            return True
        except Exception as e:
            st.error(f"Error deteniendo adquisición: {e}")
            return False
    
    def render_sidebar(self):
        """Renderizar barra lateral con controles"""
        st.sidebar.title("🌐 IoT Control Panel")
        
        # Estado de conexión
        st.sidebar.markdown("### 🔗 Estado de Conexión")
        
        # Verificar conexión con API
        try:
            health = self.make_api_request("/health")
            if health and health.get("status") == "healthy":
                st.sidebar.success("✅ Backend conectado")
                st.sidebar.metric("Dispositivos", health.get("devices_count", 0))
            else:
                st.sidebar.error("❌ Backend desconectado")
        except:
            st.sidebar.error("❌ Sin conexión")
        
        st.sidebar.markdown("---")
        
        # Controles de sistema
        st.sidebar.markdown("### ⚙️ Controles de Sistema")
        
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("🔍 Escanear Red"):
class IoTDashboard:
    """Dashboard que consulta datos directamente de Supabase"""
    def __init__(self):
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        if 'selected_device' not in st.session_state:
            st.session_state.selected_device = None

    def get_sensor_data(self, limit=100):
        try:
            response = supabase.table("sensor_data").select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            st.error(f"❌ Error consultando Supabase: {e}")
            return None

    def render_overview(self):
        st.title("🌐 IoT Dashboard - Vista General")
        data = self.get_sensor_data(100)
        if not data:
            st.error("No se pueden cargar los datos desde Supabase")
            return
        df = pd.DataFrame(data)
        if df.empty:
            st.info("No hay datos disponibles en Supabase.")
            return
        # Mostrar tabla principal
        st.markdown("### � Últimos datos de sensores")
        st.dataframe(df, use_container_width=True)
        # Métricas rápidas
        st.markdown("### 📊 Métricas rápidas")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total registros", len(df))
        with col2:
            st.metric("Última actualización", str(df['timestamp'].max()))

    def run(self):
        self.render_overview()
        st.markdown("---")
        st.markdown(
            "🌐 **IoT Streamlit Dashboard** | "
            f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        with col2:
            online_count = len([d for d in devices if d.get('status') == 'online'])
            st.metric(
                "✅ Dispositivos Online",
                online_count,
                delta=f"{online_count}/{total_devices}"
            )
        
        with col3:
            acquisition_status = "🟢 Activa" if status.get("running") else "🟡 Inactiva"
            st.metric(
                "📊 Adquisición",
                acquisition_status,
                delta=None
            )
        
        with col4:
            last_data = status.get("last_data")
            if last_data:
                last_update = datetime.fromisoformat(last_data.replace("Z", "+00:00"))
                delta_time = datetime.now() - last_update.replace(tzinfo=None)
                st.metric(
                    "🕐 Última Actualización",
                    f"{delta_time.seconds//60}m {delta_time.seconds%60}s",
                    delta="hace"
                )
            else:
                st.metric("🕐 Última Actualización", "Sin datos", delta=None)
        
        # Gráfico de estado de dispositivos
        if devices:
            st.markdown("### 📊 Estado de Dispositivos")
            
            # Preparar datos para gráfico
            status_counts = {}
            device_types = {}
            
            for device in devices:
                status = device.get('status', 'unknown')
                device_type = device.get('device_type', 'unknown')
                
                status_counts[status] = status_counts.get(status, 0) + 1
                device_types[device_type] = device_types.get(device_type, 0) + 1
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Gráfico de estado
                status_df = pd.DataFrame(list(status_counts.items()), columns=['Estado', 'Cantidad'])
                fig_status = px.pie(
                    status_df, 
                    values='Cantidad', 
                    names='Estado',
                    title="Estado de Dispositivos",
                    color_discrete_map={
                        'online': '#28a745',
                        'offline': '#dc3545',
                        'error': '#ffc107'
                    }
                )
                st.plotly_chart(fig_status, use_container_width=True)
            
            with col2:
                # Gráfico de tipos
                types_df = pd.DataFrame(list(device_types.items()), columns=['Tipo', 'Cantidad'])
                fig_types = px.bar(
                    types_df,
                    x='Tipo',
                    y='Cantidad',
                    title="Dispositivos por Tipo",
                    color='Cantidad',
                    color_continuous_scale='viridis'
                )
                st.plotly_chart(fig_types, use_container_width=True)
        
        # Tabla de dispositivos
        st.markdown("### 📱 Lista de Dispositivos")
        
        if devices:
            df = pd.DataFrame(devices)
            
            # Formatear tabla
            df_display = df[['device_id', 'device_type', 'ip_address', 'status', 'last_seen']].copy()
            df_display.columns = ['ID Dispositivo', 'Tipo', 'IP', 'Estado', 'Última Conexión']
            
            # Colorear estados
            def color_status(val):
                if val == 'online':
                    return 'background-color: #d4edda; color: #155724'
                elif val == 'offline':
                    return 'background-color: #f8d7da; color: #721c24'
                elif val == 'error':
                    return 'background-color: #fff3cd; color: #856404'
                return ''
            
            styled_df = df_display.style.applymap(color_status, subset=['Estado'])
            st.dataframe(styled_df, use_container_width=True)
            
            # Seleccionar dispositivo para detalles
            st.markdown("### 🔍 Detalles de Dispositivo")
            device_ids = [d['device_id'] for d in devices]
            selected = st.selectbox("Seleccionar dispositivo:", device_ids)
            
            if selected:
                self.render_device_details(selected)
        else:
            st.info("No hay dispositivos detectados. Usa el botón 'Escanear Red' para buscar dispositivos.")
    
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
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Gráfico temporal
            if 'sensor_data' in df.columns:
                st.markdown(f"#### 📈 Datos de {device_id}")
                
                # Intentar parsear datos del sensor
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
    
    def render_real_time_data(self):
        """Renderizar vista de datos en tiempo real"""
        st.title("📊 Datos en Tiempo Real")
        
        # Obtener datos más recientes
        latest_data = self.get_latest_data()
        
        if not latest_data or not latest_data.get("success"):
            st.error("No se pueden cargar los datos en tiempo real")
            return
        
        data = latest_data.get("data", {})
        
        # Timestamp de los datos
        timestamp = data.get('timestamp')
        if timestamp:
            st.info(f"📅 Última actualización: {timestamp}")
        
        # Datos Arduino USB
        arduino_usb = data.get('arduino_usb')
        if arduino_usb:
            st.markdown("### 🔌 Arduino USB")
            
            col1, col2 = st.columns(2)
            with col1:
                st.json(arduino_usb)
            with col2:
                # Crear gráfico si hay datos numéricos
                try:
                    if isinstance(arduino_usb, dict):
                        numeric_data = {k: v for k, v in arduino_usb.items() 
                                     if isinstance(v, (int, float))}
                        if numeric_data:
                            fig = px.bar(
                                x=list(numeric_data.keys()),
                                y=list(numeric_data.values()),
                                title="Sensores Arduino USB"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                except Exception:
                    pass
        else:
            st.info("🔌 Arduino USB: Sin datos")
        
        # Datos Arduinos Ethernet
        arduino_ethernet = data.get('arduino_ethernet', [])
        if arduino_ethernet:
            st.markdown("### 🌐 Arduinos Ethernet")
            
            for i, arduino in enumerate(arduino_ethernet):
                with st.expander(f"Arduino {arduino.get('device_id', i+1)}"):
                    st.json(arduino.get('data', {}))
        else:
            st.info("🌐 Arduinos Ethernet: Sin datos")
        
        # Datos Modbus
        modbus_devices = data.get('modbus_devices', {})
        if modbus_devices:
            st.markdown("### 🔧 Dispositivos Modbus")
            
            for device_id, device_data in modbus_devices.items():
                with st.expander(f"Dispositivo Modbus {device_id}"):
                    if device_data:
                        # Crear DataFrame para mejor visualización
                        df = pd.DataFrame(device_data)
                        st.dataframe(df, use_container_width=True)
                        
                        # Gráfico de valores
                        if 'value' in df.columns and 'address' in df.columns:
                            fig = px.bar(
                                df,
                                x='address',
                                y='value',
                                title=f"Registros Modbus - {device_id}"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Sin datos disponibles")
        else:
            st.info("🔧 Dispositivos Modbus: Sin datos")
        
        # Errores
        errors = data.get('errors', [])
        if errors:
            st.markdown("### ⚠️ Errores Recientes")
            for error in errors:
                st.error(error)
        
        # Auto-refresh para tiempo real
        if st.button("🔄 Refrescar Datos"):
            st.rerun()
        
        # Refresh automático cada 5 segundos
        time.sleep(5)
        st.rerun()
    
    def run(self):
        """Ejecutar la aplicación principal"""
        # Sidebar
        self.render_sidebar()
        
        # Navegación principal
        tab1, tab2 = st.tabs(["📋 Vista General", "📊 Tiempo Real"])
        
        with tab1:
            self.render_overview()
        
        with tab2:
            self.render_real_time_data()
        
        # Footer
        st.markdown("---")
        st.markdown(
            "🌐 **IoT Streamlit Dashboard** | "
            f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}"
        )

# Ejecutar aplicación
if __name__ == "__main__":
    dashboard = IoTDashboard()
    dashboard.run()
