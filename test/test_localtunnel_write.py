import requests
import toml
import os

def get_public_ip():
    """Obtiene la IP pública usando api.ipify.org"""
    try:
        resp = requests.get("https://api.ipify.org?format=text", timeout=5)
        if resp.status_code == 200:
            return resp.text.strip()
    except Exception as e:
        print(f"Error obteniendo IP pública: {e}")
    return None

def save_tunnel_credentials(url, public_ip, path):
    """Guarda la URL y la IP pública en un archivo .toml"""
    data = {
        'localtunnel': {
            'url': url,
            'password': public_ip
        }
    }
    with open(path, 'w') as f:
        toml.dump(data, f)
    print(f"Archivo {path} actualizado:")
    print(open(path).read())

def test_write_secrets_tunnel():
    # Simula una URL pública de LocalTunnel
    lt_url = "https://test-tunnel.loca.lt"
    public_ip = get_public_ip()
    assert public_ip, "No se pudo obtener la IP pública"
    path = os.path.join(os.path.dirname(__file__), '../secrets_tunnel.toml')
    save_tunnel_credentials(lt_url, public_ip, path)
    # Verifica que el archivo se haya escrito correctamente
    data = toml.load(path)
    assert data['localtunnel']['url'] == lt_url
    assert data['localtunnel']['password'] == public_ip
    print("Prueba exitosa: secrets_tunnel.toml contiene la URL y la IP pública correctas.")

if __name__ == "__main__":
    test_write_secrets_tunnel()
