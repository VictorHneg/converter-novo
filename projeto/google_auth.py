import os
from google.oauth2.credentials import Credentials

def get_google_drive_credentials():
    # Exemplo: lê credenciais salvas em arquivo (ajuste para seu fluxo real)
    creds_path = os.path.join(os.path.dirname(__file__), 'token.json')
    if os.path.exists(creds_path):
        creds = Credentials.from_authorized_user_file(creds_path)
        return creds
    return None
