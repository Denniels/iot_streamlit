import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os

# Colores elegantes
PRIMARY_COLOR = "#1a2639"  # Azul oscuro
ACCENT_COLOR = "#e6b800"   # Dorado
BG_COLOR = "#f5f6fa"       # Fondo claro
SUCCESS_COLOR = "#2ecc71"  # Verde confianza
ERROR_COLOR = "#e74c3c"    # Rojo

st.set_page_config(
    page_title="IoT Dashboard - Jetson & Arduino",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
    <style>
    .reportview-container {{ background: {BG_COLOR}; }}
    .sidebar .sidebar-content {{ background: {PRIMARY_COLOR}; color: white; }}
    .css-1d391kg {{ color: {PRIMARY_COLOR}; }}
    .css-1v0mbdj p {{ color: {PRIMARY_COLOR}; }}
    .st-bb {{ background: {PRIMARY_COLOR}; }}
    .st-bb:hover {{ background: {ACCENT_COLOR}; }}
    .st-bb:active {{ background: {SUCCESS_COLOR}; }}
    .st-bb:focus {{ background: {ACCENT_COLOR}; }}
    </style>
""", unsafe_allow_html=True)

st.title("IoT Dashboard - Jetson Nano & Arduino")
st.markdown(f"<h4 style='color:{ACCENT_COLOR};'>Monitoreo avanzado de dispositivos y sensores</h4>", unsafe_allow_html=True)

# Configuración Supabase
SUPABASE_URL = st.secrets["SUPABASE_URL"] if "SUPABASE_URL" in st.secrets else os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"] if "SUPABASE_ANON_KEY" in st.secrets else os.getenv("SUPABASE_ANON_KEY")

# Consulta a Supabase REST API
@st.cache_data(ttl=60)
def get_sensor_data():
    url = f"{SUPABASE_URL}/rest/v1/sensor_data?select=*"
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            st.error("Error consultando Supabase: " + r.text)
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de API: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_devices():
    url = f"{SUPABASE_URL}/rest/v1/devices?select=*"
    headers = {"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {SUPABASE_ANON_KEY}"}
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
        else:
            st.error("Error consultando Supabase: " + r.text)
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de API: {e}")
        return pd.DataFrame()

# Carga de datos
sensor_df = get_sensor_data()
devices_df = get_devices()

# Sidebar: Filtros
st.sidebar.header("Filtros avanzados")
devices = devices_df["device_id"].unique() if not devices_df.empty else []
selected_device = st.sidebar.selectbox("Selecciona dispositivo", devices)

# Últimos 5 registros por dispositivo
st.subheader("Últimos 5 registros por dispositivo")
if not sensor_df.empty:
    for device in devices:
        st.markdown(f"<h5 style='color:{PRIMARY_COLOR};'>Dispositivo: {device}</h5>", unsafe_allow_html=True)
        df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp", ascending=False).head(5)
        st.dataframe(df_device, use_container_width=True)
else:
    st.info("No hay datos de sensores disponibles.")

# Gráficas avanzadas por dispositivo
st.subheader("Gráficas avanzadas por dispositivo")
if not sensor_df.empty:
    for device in devices:
        df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp")
        if not df_device.empty:
            fig = px.line(df_device, x="timestamp", y="value", color="sensor_type", title=f"{device} - Sensores")
            fig.update_layout(plot_bgcolor=BG_COLOR, paper_bgcolor=BG_COLOR, font_color=PRIMARY_COLOR)
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No hay datos para graficar.")

# Dashboard general avanzado
st.subheader("Dashboard general avanzado")
if not sensor_df.empty:
    fig = px.scatter(sensor_df, x="timestamp", y="value", color="device_id", symbol="sensor_type", title="Historial completo de sensores")
    fig.update_layout(plot_bgcolor=BG_COLOR, paper_bgcolor=BG_COLOR, font_color=PRIMARY_COLOR)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(f"<h6 style='color:{SUCCESS_COLOR};'>Total de registros: {len(sensor_df)}</h6>", unsafe_allow_html=True)
else:
    st.info("No hay datos históricos disponibles.")


st.markdown("<small>Actualización automática cada minuto. Powered by Streamlit Cloud & Supabase.</small>", unsafe_allow_html=True)
    
    def get_system_status(self):
        # Removed duplicate and misindented methods
class IoTDashboard:
    def __init__(self):
        self.api_url = "http://api.example.com"  # Example API URL

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
                with st.spinner("Escaneando..."):
                    if self.trigger_scan():
                        st.success("Escaneo iniciado")
                    time.sleep(2)
                    st.rerun()

        with col2:
            if st.button("🔄 Actualizar"):
                st.session_state.last_update = datetime.now()
                st.rerun()

        # Control de adquisición
        st.sidebar.markdown("### 📊 Adquisición de Datos")

        status = self.get_system_status()
        if status:
            is_running = status.get("running", False)

            if is_running:
                st.sidebar.success("🟢 Adquisición activa")
                if st.sidebar.button("⏹️ Detener"):
                    if self.stop_acquisition():
                        st.success("Adquisición detenida")
                        time.sleep(1)
                        st.rerun()
            else:
                st.sidebar.warning("🟡 Adquisición inactiva")
                interval = st.sidebar.slider("Intervalo (seg)", 5, 60, 10)
                if st.sidebar.button("▶️ Iniciar"):
                    if self.start_acquisition(interval):
                        st.success("Adquisición iniciada")
                        time.sleep(1)
                        st.rerun()

        st.sidebar.markdown("---")

        # Auto-refresh
        st.sidebar.markdown("### 🔄 Auto-actualización")
        st.session_state.auto_refresh = st.sidebar.checkbox("Activar auto-refresh", st.session_state.auto_refresh)

        if st.session_state.auto_refresh:
            refresh_rate = st.sidebar.slider("Segundos", 5, 60, 10)
            st.sidebar.info(f"Próxima actualización en {refresh_rate}s")

            # Placeholder para countdown
            placeholder = st.sidebar.empty()
            for i in range(refresh_rate, 0, -1):
                placeholder.text(f"Actualizando en {i}s...")
                time.sleep(1)
            placeholder.text("Actualizando...")
            st.rerun()

    def render_overview(self):
        """Renderizar vista general del sistema"""
        st.title("🌐 IoT Dashboard - Vista General")

        # Obtener datos del sistema
        status = self.get_system_status()
        devices_response = self.get_devices()

        if not status or not devices_response:
            st.error("No se pueden cargar los datos del sistema")
            return

        devices = devices_response.get("data", [])

        # Métricas principales
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_devices = len(devices)
            st.metric(
                "📱 Total Dispositivos",
                total_devices,
                delta=None
            )

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
            f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}")

# Ejecutar aplicación
if __name__ == "__main__":
    dashboard = IoTDashboard()
    dashboard.run()
