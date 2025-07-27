import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import os
import time

from datetime import datetime

# Inicializar variable de sesión para la última actualización
if "last_update" not in st.session_state:
    st.session_state.last_update = datetime.now()
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
# Esquema visual del flujo de datos (tarjetas separadas y flechas pequeñas, responsive)
st.markdown(f"""
<div style='width:100%; max-width:1200px; margin:auto; margin-bottom:32px; padding:0 10px;'>
  <svg width='100%' height='150' viewBox='0 0 1200 150' fill='none' xmlns='http://www.w3.org/2000/svg' style='max-width:100%;'>
    <g font-family='sans-serif' font-size='20' font-weight='bold'>
      <!-- Tarjeta Sensores -->
      <rect x='30' y='40' width='260' height='70' rx='35' fill='{ACCENT_COLOR}' opacity='0.18'/>
      <text x='160' y='80' text-anchor='middle' fill='{PRIMARY_COLOR}'>Sensores</text>
      <text x='160' y='135' text-anchor='middle' fill='{PRIMARY_COLOR}' font-size='15' font-weight='normal'>Captura</text>
      <!-- Tarjeta Jetson/PostgreSQL -->
      <rect x='340' y='40' width='320' height='70' rx='35' fill='{ACCENT_COLOR}' opacity='0.18'/>
      <text x='500' y='80' text-anchor='middle' fill='{PRIMARY_COLOR}'>Jetson Nano / PostgreSQL</text>
      <text x='500' y='135' text-anchor='middle' fill='{PRIMARY_COLOR}' font-size='15' font-weight='normal'>Almacenamiento local</text>
      <!-- Tarjeta Supabase -->
      <rect x='700' y='40' width='260' height='70' rx='35' fill='{ACCENT_COLOR}' opacity='0.18'/>
      <text x='830' y='80' text-anchor='middle' fill='{PRIMARY_COLOR}'>Supabase Cloud</text>
      <text x='830' y='135' text-anchor='middle' fill='{PRIMARY_COLOR}' font-size='15' font-weight='normal'>Sincronización cloud</text>
      <!-- Tarjeta Streamlit -->
      <rect x='1010' y='40' width='160' height='70' rx='35' fill='{ACCENT_COLOR}' opacity='0.18'/>
      <text x='1090' y='80' text-anchor='middle' fill='{PRIMARY_COLOR}'>Streamlit Cloud</text>
      <text x='1090' y='135' text-anchor='middle' fill='{PRIMARY_COLOR}' font-size='15' font-weight='normal'>Visualización y compartición</text>
      <!-- Flechas pequeñas -->
      <path d='M290,75 L340,75' stroke='{PRIMARY_COLOR}' stroke-width='2.5' marker-end='url(#arrowhead)'/>
      <path d='M660,75 L700,75' stroke='{PRIMARY_COLOR}' stroke-width='2.5' marker-end='url(#arrowhead)'/>
      <path d='M960,75 L1010,75' stroke='{PRIMARY_COLOR}' stroke-width='2.5' marker-end='url(#arrowhead)'/>
      <defs>
        <marker id='arrowhead' markerWidth='8' markerHeight='6' refX='8' refY='3' orient='auto'>
          <polygon points='0 0, 8 3, 0 6' fill='{PRIMARY_COLOR}' />
        </marker>
      </defs>
    </g>
  </svg>
</div>
""", unsafe_allow_html=True)

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
# Detectar dispositivos activos desde los datos de sensores si la tabla de dispositivos está vacía
if not devices_df.empty:
    devices = devices_df["device_id"].unique()
else:
    # Si la tabla de dispositivos está vacía, usar los device_id presentes en los datos de sensores
    devices = sensor_df["device_id"].unique() if not sensor_df.empty else []
if len(devices) == 0:
    st.sidebar.warning("No hay dispositivos detectados. Verifica la conexión o espera la próxima actualización.")
selected_device = st.sidebar.selectbox("Selecciona dispositivo", devices)

# Últimos 5 registros por dispositivo
st.subheader("🔎 Últimos 5 registros por dispositivo")
st.markdown("<small>Esta tabla muestra los datos más recientes recibidos de cada dispositivo conectado. Útil para monitoreo rápido y diagnóstico inmediato. Si no ves dispositivos, revisa la conexión y el pipeline.</small>", unsafe_allow_html=True)
if not sensor_df.empty and len(devices) > 0:
    for device in devices:
        st.markdown(f"<h5 style='color:{ACCENT_COLOR};'>Dispositivo: <b>{device}</b></h5>", unsafe_allow_html=True)
        df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp", ascending=False).head(5)
        if not df_device.empty:
            st.dataframe(df_device, use_container_width=True)
        else:
            st.info(f"No hay registros recientes para {device}.")
else:
    st.info("No hay datos de sensores disponibles o no hay dispositivos detectados.")

# Gráficas avanzadas por dispositivo
st.subheader("📈 Gráficas avanzadas por dispositivo")
st.markdown("<small>Visualiza la evolución temporal de cada sensor en cada dispositivo y la proporción de registros por tipo de sensor. Permite identificar tendencias, anomalías y comparar el comportamiento de los sensores. Si no ves gráficas, revisa que los dispositivos estén enviando datos.</small>", unsafe_allow_html=True)
if not sensor_df.empty and len(devices) > 0:
    for i, device in enumerate(devices):
        df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp")
        if not df_device.empty:
            col1, col2 = st.columns([2,1])
            with col1:
                fig = px.line(
                    df_device,
                    x="timestamp",
                    y="value",
                    color="sensor_type",
                    title=f"📊 {device}: Evolución temporal de sensores",
                    labels={"timestamp": "Fecha y hora", "value": "Valor", "sensor_type": "Tipo de sensor"},
                    template="plotly_white",
                    line_shape="spline"
                )
                fig.update_layout(
                    plot_bgcolor=BG_COLOR,
                    paper_bgcolor=BG_COLOR,
                    font_color=PRIMARY_COLOR,
                    legend_title_text="Sensor",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    title_font=dict(size=20, color=ACCENT_COLOR)
                )
                fig.update_traces(line=dict(width=4), marker=dict(size=10))
                st.plotly_chart(fig, use_container_width=True, key=f"plot_{device}_{i}")
            with col2:
                pie_df = df_device["sensor_type"].value_counts().reset_index()
                pie_df.columns = ["Tipo de sensor", "Registros"]
                fig_pie = px.pie(
                    pie_df,
                    names="Tipo de sensor",
                    values="Registros",
                    title=f"Proporción por tipo de sensor en {device}",
                    color_discrete_sequence=px.colors.sequential.YlOrBr
                )
                fig_pie.update_traces(textinfo='percent+label')
                fig_pie.update_layout(title_font=dict(size=16, color=ACCENT_COLOR))
                st.plotly_chart(fig_pie, use_container_width=True, key=f"pie_{device}_{i}")
        else:
            st.warning(f"No hay datos para graficar en {device}.")
else:
    st.info("No hay datos para graficar o no hay dispositivos detectados.")

# Dashboard general avanzado
st.subheader("🌐 Dashboard general avanzado")
st.markdown("<small>Visualización profesional del historial completo de sensores y dispositivos. Incluye distribución de valores, proporción de registros por dispositivo y evolución temporal. Si no ves datos, revisa la conexión y el pipeline.</small>", unsafe_allow_html=True)
if not sensor_df.empty and len(devices) > 0:
    col1, col2 = st.columns([2,1])
    with col1:
        fig = px.scatter(
            sensor_df,
            x="timestamp",
            y="value",
            color="device_id",
            symbol="sensor_type",
            title="🌐 Historial completo de sensores y dispositivos",
            hover_data=["sensor_type", "value", "unit", "device_id"],
            labels={"timestamp": "Fecha y hora", "value": "Valor", "device_id": "Dispositivo", "sensor_type": "Tipo de sensor"},
            template="plotly_white"
        )
        fig.update_layout(
            plot_bgcolor=BG_COLOR,
            paper_bgcolor=BG_COLOR,
            font_color=PRIMARY_COLOR,
            legend_title_text="Dispositivo",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            title_font=dict(size=22, color=ACCENT_COLOR)
        )
        fig.update_traces(marker=dict(size=14, line=dict(width=3, color=ACCENT_COLOR)))
        st.plotly_chart(fig, use_container_width=True, key="general_scatter_dashboard")
        st.markdown(f"<h6 style='color:{SUCCESS_COLOR};'>Total de registros: {len(sensor_df)}</h6>", unsafe_allow_html=True)
    with col2:
        # Gráfico de torta: proporción de registros por dispositivo
        pie_df = sensor_df["device_id"].value_counts().reset_index()
        pie_df.columns = ["Dispositivo", "Registros"]
        fig_pie = px.pie(
            pie_df,
            names="Dispositivo",
            values="Registros",
            title="Proporción de registros por dispositivo",
            color_discrete_sequence=px.colors.sequential.YlOrBr
        )
        fig_pie.update_traces(textinfo='percent+label')
        fig_pie.update_layout(title_font=dict(size=16, color=ACCENT_COLOR))
        st.plotly_chart(fig_pie, use_container_width=True, key="pie_dashboard")
    # Histograma de valores
    st.markdown("#### Distribución de valores de sensores")
    hist_fig = px.histogram(
        sensor_df,
        x="value",
        color="sensor_type",
        nbins=30,
        title="Histograma de valores por tipo de sensor",
        labels={"value": "Valor", "sensor_type": "Tipo de sensor"},
        template="plotly_white"
    )
    hist_fig.update_layout(
        plot_bgcolor=BG_COLOR,
        paper_bgcolor=BG_COLOR,
        font_color=PRIMARY_COLOR,
        legend_title_text="Sensor",
        title_font=dict(size=18, color=ACCENT_COLOR)
    )
    st.plotly_chart(hist_fig, use_container_width=True, key="hist_dashboard")
else:
    st.info("No hay datos históricos disponibles o no hay dispositivos detectados.")


st.markdown("<small>Actualización automática cada minuto. Powered by Streamlit Cloud & Supabase.</small>", unsafe_allow_html=True)

class IoTDashboard:
    def __init__(self):
        pass

    def render_sidebar(self):
        if "auto_refresh" not in st.session_state:
            st.session_state.auto_refresh = False
        """Renderizar barra lateral con controles"""
        st.sidebar.title("🌐 IoT Control Panel")
        st.sidebar.markdown("### 🔗 Estado de Conexión")
        st.sidebar.success("✅ Conectado a Supabase")
        # Mostrar el número de dispositivos detectados desde los datos de sensores si la tabla está vacía
        try:
            if not devices_df.empty:
                devices_count = len(devices_df)
            else:
                devices_count = len(sensor_df["device_id"].unique()) if not sensor_df.empty else 0
            st.sidebar.metric("Dispositivos", devices_count)
        except Exception:
            st.sidebar.metric("Dispositivos", 0)
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚙️ Controles de Sistema")
        if st.button("🔄 Actualizar"):
            st.rerun()
        st.sidebar.markdown("---")
        st.sidebar.markdown("### ⚡ Visualización en Tiempo Real")
        prev_real_time = st.session_state.get("real_time", False)
        st.session_state.real_time = st.sidebar.toggle("Activar modo tiempo real", value=prev_real_time)
        # Control de adquisición Jetson Nano mediante archivo local
        control_flag_path = "/home/daniel/repos/iot_streamlit/acquisition_control.flag"
        try:
            if st.session_state.real_time != prev_real_time:
                # Si el estado cambió, escribir el flag
                with open(control_flag_path, "w") as f:
                    f.write("ON" if st.session_state.real_time else "OFF")
        except Exception as e:
            st.sidebar.error(f"Error control Jetson Nano: {e}")
        if st.session_state.real_time:
            st.sidebar.info("La Jetson Nano está adquiriendo y enviando datos en tiempo real.")
            st.session_state.refresh_rate = st.sidebar.slider("Intervalo de actualización (segundos)", 2, 60, st.session_state.get("refresh_rate", 10))
            st.sidebar.success(f"Actualizando cada {st.session_state.refresh_rate}s")
            placeholder = st.sidebar.empty()
            for i in range(st.session_state.refresh_rate, 0, -1):
                placeholder.text(f"Actualizando en {i}s...")
                time.sleep(1)
            placeholder.text("Actualizando...")
            st.rerun()
        else:
            st.sidebar.warning("Modo tiempo real desactivado. La Jetson Nano puede pausar la adquisición y ahorrar recursos.")

    def render_overview(self):
        """Renderizar vista general del sistema"""
        st.title("🌐 IoT Dashboard - Vista General")
        # Usar devices_df y sensor_df directamente
        if devices_df.empty:
            st.error("No se pueden cargar los datos de dispositivos")
            return
        devices = devices_df.to_dict(orient="records")

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
            # Asegura que 'status' esté definido como dict vacío si no existe
            try:
                acquisition_status = "🟢 Activa" if status.get("running") else "🟡 Inactiva"
            except UnboundLocalError:
                status = {}
                acquisition_status = "🟡 Inactiva"
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

        # Obtener datos más recientes desde Supabase
        sensor_df = get_sensor_data()
        if sensor_df.empty:
            st.error("No se pueden cargar los datos en tiempo real")
            return

        # Mostrar los últimos 5 registros por dispositivo
        st.subheader("Últimos 5 registros por dispositivo (Tiempo Real)")
        devices = sensor_df["device_id"].unique()
        for device in devices:
            st.markdown(f"<h5 style='color:{PRIMARY_COLOR};'>Dispositivo: {device}</h5>", unsafe_allow_html=True)
            df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp", ascending=False).head(5)
            st.dataframe(df_device, use_container_width=True)

        # Gráficas avanzadas por dispositivo
        st.subheader("Gráficas avanzadas por dispositivo (Tiempo Real)")
        for i, device in enumerate(devices):
            df_device = sensor_df[sensor_df["device_id"] == device].sort_values("timestamp")
            if not df_device.empty:
                fig = px.line(df_device, x="timestamp", y="value", color="sensor_type", title=f"{device} - Sensores")
                fig.update_layout(plot_bgcolor=BG_COLOR, paper_bgcolor=BG_COLOR, font_color=PRIMARY_COLOR)
                st.plotly_chart(fig, use_container_width=True, key=f"realtime_plot_{device}_{i}")

        # Dashboard general avanzado
        st.subheader("Dashboard general avanzado (Tiempo Real)")
        fig = px.scatter(sensor_df, x="timestamp", y="value", color="device_id", symbol="sensor_type", title="Historial completo de sensores")
        fig.update_layout(plot_bgcolor=BG_COLOR, paper_bgcolor=BG_COLOR, font_color=PRIMARY_COLOR)
        st.plotly_chart(fig, use_container_width=True, key="realtime_general_scatter")
        st.markdown(f"<h6 style='color:{SUCCESS_COLOR};'>Total de registros: {len(sensor_df)}</h6>", unsafe_allow_html=True)

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
