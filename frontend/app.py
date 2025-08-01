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


# --- Detección automática y robusta de la URL pública de Cloudflare Tunnel ---
# Usar la última URL pública conocida (puedes poner aquí la última URL conocida o dejarlo vacío para forzar la detección)
DEFAULT_CF_URL = "https://huge-variations-wb-iraq.trycloudflare.com"

def get_public_cf_url():
    # Intenta obtener la URL pública desde el endpoint /cf_url de la URL pública conocida
    try:
        resp = requests.get(f"{DEFAULT_CF_URL}/cf_url", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('cf_url'):
                return data['cf_url']
    except Exception:
        pass
    return None



# Siempre intenta descubrir la URL pública automáticamente y actualizar si cambia
if 'api_url' not in st.session_state:
    st.session_state['api_url'] = None

auto_url = get_public_cf_url()
if auto_url and auto_url != st.session_state['api_url']:
    st.session_state['api_url'] = auto_url
    st.sidebar.success(f"URL pública activa: {auto_url}")
elif st.session_state['api_url']:
    st.sidebar.success(f"URL pública activa: {st.session_state['api_url']}")
else:
    st.sidebar.error("No se pudo detectar la URL pública de Cloudflare Tunnel. Esperando a que esté disponible...")

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

    def get_sensor_data(self, limit=500):
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
            url = f"{API_URL}/devices"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                devices = data.get('data', [])
                device_ids = [d['device_id'] for d in devices if 'device_id' in d]
                st.sidebar.write(f"🔍 Dispositivos detectados: {len(device_ids)}")
                for device in device_ids:
                    st.sidebar.write(f"  • {device}")
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
        
        data = self.get_sensor_data(200)
        if not data:
            st.error("No se pueden cargar los datos desde la API Jetson")
            return
        df = pd.DataFrame(data)
        if 'raw_data' in df.columns:
            df['raw_data'] = df['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))
        if df.empty:
            st.info("No hay datos disponibles en la API Jetson.")
            return

        # Selección de dispositivo (mostrar todos los device_id únicos)
        st.markdown("### 📱 Selecciona un dispositivo para visualizar sus datos")
        device_ids = self.get_all_devices()
        st.info(f"📊 Dispositivos disponibles: {len(device_ids)}")
        for device in device_ids:
            device_type = "🔌 USB" if "usb" in device.lower() else "🌐 Ethernet" if "ethernet" in device.lower() else "❓ Desconocido"
            count = len([row for row in df.to_dict('records') if row.get('device_id') == device])
            st.write(f"{device_type} **{device}** - {count} registros")
        selected_device = st.selectbox("Dispositivo:", device_ids, key="device_selector")

        # Si no hay datos recientes, buscar los últimos datos históricos del dispositivo seleccionado
        df_device = df[df['device_id'] == selected_device]
        if df_device.empty:
            # Buscar los últimos datos históricos del dispositivo desde la API
            try:
                url = f"{API_URL}/data/{selected_device}?limit=50"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data_hist = resp.json().get('data', [])
                    df_device = pd.DataFrame(data_hist)
                else:
                    df_device = pd.DataFrame()
            except Exception:
                df_device = pd.DataFrame()

        # Mostrar tabla principal filtrada o mensaje si no hay datos
        st.markdown(f"### Últimos datos de sensores - {selected_device}")
        if 'raw_data' in df_device.columns:
            df_device['raw_data'] = df_device['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))
        if df_device.empty:
            st.info(f"No hay datos disponibles para {selected_device} en la API Jetson.")
        else:
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

        # --- Filtro de rango temporal ---
        st.markdown("### ⏳ Filtro de rango temporal")
        rango_opciones = [
            "Tiempo real (últimos 10 min)",
            "Hoy",
            "Semana",
            "Mes",
            "Año",
            "Personalizado"
        ]
        rango_seleccionado = st.selectbox("Selecciona el rango de tiempo a visualizar:", rango_opciones, key="rango_temporal")
        df_device['timestamp'] = pd.to_datetime(df_device['timestamp'])
        ahora = pd.Timestamp.now(tz=df_device['timestamp'].dt.tz if df_device['timestamp'].dt.tz is not None else None)
        if rango_seleccionado == "Tiempo real (últimos 10 min)":
            inicio = ahora - pd.Timedelta(minutes=10)
            df_device_filtrado = df_device[df_device['timestamp'] >= inicio]
        elif rango_seleccionado == "Hoy":
            inicio = ahora.normalize()
            df_device_filtrado = df_device[df_device['timestamp'] >= inicio]
        elif rango_seleccionado == "Semana":
            inicio = ahora - pd.Timedelta(days=7)
            df_device_filtrado = df_device[df_device['timestamp'] >= inicio]
        elif rango_seleccionado == "Mes":
            inicio = ahora - pd.Timedelta(days=30)
            df_device_filtrado = df_device[df_device['timestamp'] >= inicio]
        elif rango_seleccionado == "Año":
            inicio = ahora - pd.Timedelta(days=365)
            df_device_filtrado = df_device[df_device['timestamp'] >= inicio]
        elif rango_seleccionado == "Personalizado":
            min_fecha = df_device['timestamp'].min()
            max_fecha = df_device['timestamp'].max()
            rango_slider = st.slider(
                "Selecciona el rango de fechas:",
                min_value=min_fecha,
                max_value=max_fecha,
                value=(min_fecha, max_fecha),
                format="YYYY-MM-DD HH:mm"
            )
            df_device_filtrado = df_device[(df_device['timestamp'] >= rango_slider[0]) & (df_device['timestamp'] <= rango_slider[1])]
        else:
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
                    # Clasificar registros por rango (ajustado para datos reales)
                    def temp_rango(val):
                        if val <= 35:
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
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
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
