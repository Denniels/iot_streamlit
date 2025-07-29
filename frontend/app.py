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
from streamlit_autorefresh import st_autorefresh

# Configuración de página
st_autorefresh(interval=30 * 1000, key="data_refresh")
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
    """Dashboard que consulta datos directamente de Supabase"""
    def __init__(self):
        if 'last_update' not in st.session_state:
            st.session_state.last_update = datetime.now()
        if 'auto_refresh' not in st.session_state:
            st.session_state.auto_refresh = False
        if 'selected_device' not in st.session_state:
            st.session_state.selected_device = None

    def get_sensor_data(self, limit=500):
        try:
            # Consulta robusta que incluye todos los dispositivos con más registros
            response = supabase.table("sensor_data").select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            st.error(f"❌ Error consultando Supabase: {e}")
            st.error(f"Detalles del error: {str(e)}")
            return None

    def get_all_devices(self):
        """Obtener todos los device_id únicos en Supabase y mostrar ambos tipos aunque no tengan datos recientes"""
        try:
            response = supabase.table("sensor_data").select("device_id").execute()
            devices = set()
            if response.data:
                for row in response.data:
                    if row.get('device_id'):
                        devices.add(row['device_id'])
            # Forzar mostrar ambos tipos si existen en la red
            # USB
            usb_id = 'arduino_usb_001'
            ethernet_id = 'arduino_ethernet_192_168_0_110'
            # Puedes agregar más device_id conocidos aquí si tienes más
            devices.update([usb_id, ethernet_id])
            devices = sorted(list(devices))
            st.sidebar.write(f"🔍 Dispositivos detectados: {len(devices)}")
            for device in devices:
                st.sidebar.write(f"  • {device}")
            return devices
        except Exception as e:
            st.sidebar.error(f"❌ Error obteniendo lista de dispositivos: {e}")
            return []
    def get_service_status(self):
        """Obtiene el estado de los servicios systemd relevantes y los muestra en el dashboard"""
        import subprocess
        services = [
            ('acquire_data.service', 'Adquisición USB'),
            ('backend_api.service', 'API Backend'),
            ('sync_to_supabase.service', 'Sync Supabase')
        ]
        status_dict = {}
        for svc, label in services:
            try:
                result = subprocess.run([
                    'systemctl', 'is-active', svc
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                status = result.stdout.strip()
                status_dict[label] = status
            except Exception as e:
                status_dict[label] = f"Error: {e}"
        return status_dict

    def verify_supabase_connection(self):
        """Verifica la conexión con Supabase y muestra estadísticas"""
        try:
            # Consulta básica para verificar conexión
            response = supabase.table("sensor_data").select("device_id", count="exact").execute()
            
            st.sidebar.success("✅ Conexión con Supabase establecida")
            st.sidebar.write(f"📊 Total de registros: {response.count}")
            
            # Obtener estadísticas por dispositivo
            device_stats = supabase.table("sensor_data").select("device_id", count="exact").execute()
            
            return True
        except Exception as e:
            st.sidebar.error(f"❌ Error de conexión con Supabase: {e}")
            return False

    def render_overview(self):
        st.title("🌐 IoT Dashboard - Vista General")
        st.markdown("""
<div style='text-align: center;'>
<b>🔄 Pipeline IoT End-to-End</b><br>
<span style='font-size: 1.1em;'>
🟦 <b>Arduino</b> &rarr; 🖥️ <b>Jetson Nano (PostgreSQL)</b> &rarr; ☁️ <b>Supabase Cloud</b> &rarr; 📊 <b>Streamlit Dashboard</b>
</span><br>
<i>Captura &rarr; Almacenamiento local &rarr; Sincronización cloud &rarr; Visualización en tiempo real</i>
</div>
""", unsafe_allow_html=True)
        # Estado de servicios systemd
        st.markdown("## 🛠️ Estado de Servicios")
        status_dict = self.get_service_status()
        cols = st.columns(len(status_dict))
        for i, (label, status) in enumerate(status_dict.items()):
            color = "#28a745" if status == "active" else ("#ffc107" if status == "activating" else "#dc3545")
            cols[i].markdown(f"<div style='background:{color};padding:0.5rem;border-radius:0.5rem;text-align:center;color:white;'><b>{label}</b><br>{status}</div>", unsafe_allow_html=True)
        
        # Verificar conexión con Supabase
        if not self.verify_supabase_connection():
            st.error("No se puede conectar con Supabase. Verifique la configuración.")
            return
        
        data = self.get_sensor_data(200)
        if not data:
            st.error("No se pueden cargar los datos desde Supabase")
            return
        df = pd.DataFrame(data)
        if 'raw_data' in df.columns:
            df['raw_data'] = df['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))
        if df.empty:
            st.info("No hay datos disponibles en Supabase.")
            return

        # Selección de dispositivo (mostrar todos los device_id únicos en Supabase)
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
            # Buscar los últimos datos históricos del dispositivo
            data_hist = supabase.table("sensor_data").select("*").eq("device_id", selected_device).order("timestamp", desc=True).limit(50).execute()
            if data_hist.data:
                df_device = pd.DataFrame(data_hist.data)
            else:
                df_device = pd.DataFrame()

        # Mostrar tabla principal filtrada o mensaje si no hay datos
        st.markdown(f"### Últimos datos de sensores - {selected_device}")
        if 'raw_data' in df_device.columns:
            df_device['raw_data'] = df_device['raw_data'].apply(lambda x: json.dumps(x) if isinstance(x, dict) else str(x))
        if df_device.empty:
            st.info(f"No hay datos disponibles para {selected_device} en Supabase.")
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

        # Visualización de variables
        st.markdown("### 📈 Gráficos de variables")
        if not df_device.empty and 'sensor_type' in df_device.columns and 'value' in df_device.columns:
            sensor_types = df_device['sensor_type'].unique().tolist()
            for sensor in sensor_types:
                df_sensor = df_device[df_device['sensor_type'] == sensor]
                fig = px.line(
                    df_sensor,
                    x='timestamp',
                    y='value',
                    title=f"{sensor} - {selected_device}",
                    markers=True
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay variables numéricas para graficar.")

    def run(self):
        self.render_overview()
        st.markdown("---")
        st.markdown(
            "🌐 **IoT Streamlit Dashboard** | "
            f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")

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
    
    def get_device_data(self, device_id, hours=24):
        """Obtener datos específicos de un dispositivo con fallback para datos históricos"""
        try:
            # Primero buscar datos recientes
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            response = supabase.table("sensor_data").select("*").eq("device_id", device_id).gte("timestamp", cutoff_time.isoformat()).order("timestamp", desc=True).limit(500).execute()
            
            # Si no hay datos recientes, buscar los últimos registros del dispositivo
            if not response.data:
                st.warning(f"⚠️ No hay datos recientes para {device_id}. Buscando últimos registros...")
                response = supabase.table("sensor_data").select("*").eq("device_id", device_id).order("timestamp", desc=True).limit(100).execute()
            
            return {"success": True, "data": response.data}
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
    
    
    def run(self):
        """Ejecutar la aplicación principal"""
        # Solo vista general
        self.render_overview()
        # Footer
        st.markdown("---")
        st.markdown(
            "🌐 **IoT Streamlit Dashboard** | "
            f"Última actualización: {st.session_state.last_update.strftime('%H:%M:%S')}")

# Ejecutar aplicación
if __name__ == "__main__":
    dashboard = IoTDashboard()
    dashboard.run()
