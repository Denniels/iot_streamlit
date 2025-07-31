import subprocess
from typing import Dict

SERVICES = {
    'acquire_data.service': 'Adquisición de Datos',
    'backend_api.service': 'API Backend',
}

def get_services_status() -> Dict[str, Dict]:
    status_dict = {}
    for svc, label in SERVICES.items():
        try:
            result = subprocess.run([
                'systemctl', 'is-active', svc
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            status = result.stdout.strip()
            if status == 'active':
                semaforo = ('🟢', 'Verde', '#28a745')
            elif status in ('activating', 'reloading', 'deactivating'):
                semaforo = ('🟡', 'Amarillo', '#ffc107')
            elif status == 'failed':
                semaforo = ('🔴', 'Rojo', '#dc3545')
            else:
                semaforo = ('🔴', 'Rojo', '#dc3545')
            status_dict[label] = {
                'status': status,
                'semaforo': semaforo
            }
        except Exception as e:
            status_dict[label] = {
                'status': f"Error: {e}",
                'semaforo': ('❓', 'Desconocido', '#6c757d')
            }
    return status_dict
