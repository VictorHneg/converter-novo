import os

# Só permite HTTP localmente, nunca em produção
if os.environ.get("FLASK_ENV") != "production":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, send_file, flash, redirect, url_for, session
import tempfile
from datetime import datetime
import secrets
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
import docx
import markdown_converter  # Certifique-se de que markdown_converter.py existe na mesma pasta

# Importa seu código original
from markdown_converter import MarkdownToDocxConverter
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Configurações do Google Drive
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'openid',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email'
]
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.json')

# Instancia seu conversor original
converter = MarkdownToDocxConverter()

def get_google_drive_service():
    """Obtém o serviço do Google Drive autenticado"""
    print("get_google_drive_service: Iniciando obtenção do serviço Google Drive")
    creds = None
    if 'credentials' in session:
        print("get_google_drive_service: Credenciais encontradas na sessão")
        scopes = session['credentials'].get('scopes')
        print(f"get_google_drive_service: Escopos usados: {scopes}")
        print(f"get_google_drive_service: Conteúdo das credenciais: {session['credentials']}")
        creds = Credentials.from_authorized_user_info(session['credentials'], scopes)
        print(f"get_google_drive_service: creds.valid={creds.valid}, creds.expired={creds.expired}, creds.refresh_token={creds.refresh_token}")
    else:
        print("get_google_drive_service: Nenhuma credencial na sessão")
    
    if not creds or not creds.valid:
        print("get_google_drive_service: Credenciais inválidas ou ausentes")
        if creds:
            if creds.expired:
                print("get_google_drive_service: Token expirado")
            if not creds.refresh_token:
                print("get_google_drive_service: Não há refresh_token disponível")
        if creds and creds.expired and creds.refresh_token:
            print("get_google_drive_service: Tentando atualizar o token")
            creds.refresh(Request())
            print(f"get_google_drive_service: Após refresh, creds.valid={creds.valid}, creds.expired={creds.expired}")
        else:
            print("get_google_drive_service: Não foi possível obter credenciais válidas")
            return None
    
    print("get_google_drive_service: Serviço Google Drive criado com sucesso")
    return build('drive', 'v3', credentials=creds)

def extract_text_from_drive_doc(service, file_id):
    """Extrai texto de um documento do Google Drive"""
    print(f"extract_text_from_drive_doc: Extraindo texto do arquivo {file_id}")
    try:
        # Descobre o tipo MIME do arquivo
        file_metadata = service.files().get(fileId=file_id, fields='mimeType,name').execute()
        mime_type = file_metadata.get('mimeType')
        print(f"extract_text_from_drive_doc: mimeType do arquivo: {mime_type}")

        if mime_type == 'application/vnd.google-apps.document':
            # Google Docs: exporta como docx
            request = service.files().export_media(
                fileId=file_id,
                mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            file_content = request.execute()
            print("extract_text_from_drive_doc: Download como .docx bem-sucedido (Google Docs)")
        else:
            # Outros arquivos (ex: .docx enviado): baixa direto
            request = service.files().get_media(fileId=file_id)
            file_content = request.execute()
            print("extract_text_from_drive_doc: Download direto bem-sucedido (arquivo enviado)")

        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        markdown_text = converter.extract_text_from_docx(temp_file_path)
        os.unlink(temp_file_path)
        print("extract_text_from_drive_doc: Extração de texto concluída")
        return markdown_text
    except HttpError as e:
        print(f"extract_text_from_drive_doc: HttpError {e.resp.status} - {e}")
        raise e

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/auth')
def auth():
    """Inicia o processo de autenticação do Google"""
    print("auth: Iniciando autenticação OAuth")
    session.pop('credentials', None)
    session.pop('state', None)
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print("auth: CLIENT_SECRETS_FILE não encontrado")
        flash('Arquivo de credenciais do Google não encontrado. Configure as credenciais primeiro.', 'error')
        return redirect(url_for('index'))
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('oauth_callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # <-- Adicione esta linha
    )
    session['state'] = state
    print(f"auth: Redirecionando para {authorization_url}")
    return redirect(authorization_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Callback da autenticação OAuth"""
    print("oauth_callback: Callback recebido")
    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=session.get('state'),
            redirect_uri=url_for('oauth_callback', _external=True)
        )
        print("oauth_callback: Buscando token OAuth")
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        print(f"oauth_callback: Token recebido, escopos: {credentials.scopes}")
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        flash('Autenticação realizada com sucesso!', 'success')
        print("oauth_callback: Autenticação realizada com sucesso")
        return redirect(url_for('index'))
    except Exception as e:
        print(f"oauth_callback: Erro na autenticação: {str(e)}")
        session.pop('credentials', None)
        session.pop('state', None)
        flash(f'Erro na autenticação: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/convert', methods=['POST'])
def convert():
    """Converte o documento do Google Drive e envia para o Drive do usuário"""
    print("convert: Iniciando conversão")
    if 'credentials' not in session:
        print("convert: Usuário não autenticado")
        flash('Você precisa se autenticar primeiro.', 'error')
        return redirect(url_for('index'))
    file_id = request.form.get('file_id', '').strip()
    print(f"convert: file_id recebido: {file_id}")
    if not file_id:
        print("convert: ID de arquivo inválido")
        flash('Por favor, forneça um ID de arquivo válido.', 'error')
        return redirect(url_for('index'))
    try:
        service = get_google_drive_service()
        if not service:
            print("convert: Erro ao obter serviço Google Drive")
            flash('Erro na autenticação. Tente novamente.', 'error')
            return redirect(url_for('auth'))
        file_metadata = service.files().get(fileId=file_id).execute()
        filename = file_metadata.get('name', 'documento')
        print(f"convert: Nome do arquivo: {filename}")
        markdown_text = extract_text_from_drive_doc(service, file_id)
        doc_bytes = converter.parse_markdown_to_docx(markdown_text, '', None)
        output_filename = f"{filename}_formatado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        print(f"convert: Enviando arquivo {output_filename} para o Google Drive")

        # Salva o arquivo temporariamente para upload e lê para memória
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_file:
            temp_file.write(doc_bytes.read())
            temp_file_path = temp_file.name

        # Lê o conteúdo do arquivo para memória e fecha o arquivo
        with open(temp_file_path, 'rb') as f:
            file_data = f.read()
        os.unlink(temp_file_path)

        # Faz upload para o Google Drive a partir da memória
        media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', resumable=False)
        uploaded = service.files().create(
            body={
                'name': output_filename,
                'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            },
            media_body=media,
            fields='id,webViewLink'
        ).execute()

        file_link = uploaded.get('webViewLink')
        print(f"convert: Arquivo enviado para o Drive: {file_link}")

        flash(f'Arquivo convertido enviado para seu Google Drive! <a href="{file_link}" target="_blank">Abrir no Drive</a>', 'success')
        return redirect(url_for('index'))
    except HttpError as e:
        print(f"convert: HttpError {e.resp.status} - {e}")
        if e.resp.status == 404:
            flash('Arquivo não encontrado. Verifique se o ID está correto e se você tem acesso ao arquivo.', 'error')
        elif e.resp.status == 403:
            flash('Acesso negado. Verifique se você tem permissão para acessar este arquivo.', 'error')
        else:
            flash(f'Erro do Google Drive: {str(e)}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"convert: Erro durante a conversão: {str(e)}")
        flash(f'Erro durante a conversão: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/convert_folder', methods=['POST'])
def convert_folder():
    """Converte todos os arquivos .docx e Google Docs de uma pasta do Google Drive e faz upload dos convertidos na mesma pasta"""
    print("convert_folder: Iniciando conversão em lote")
    if 'credentials' not in session:
        print("convert_folder: Usuário não autenticado")
        flash('Você precisa se autenticar primeiro.', 'error')
        return redirect(url_for('index'))
    folder_id = request.form.get('folder_id', '').strip()
    print(f"convert_folder: folder_id recebido: {folder_id}")
    if not folder_id:
        print("convert_folder: ID de pasta inválido")
        flash('Por favor, forneça um ID de pasta válido.', 'error')
        return redirect(url_for('index'))
    try:
        service = get_google_drive_service()
        if not service:
            print("convert_folder: Erro ao obter serviço Google Drive")
            flash('Erro na autenticação. Tente novamente.', 'error')
            return redirect(url_for('auth'))

        # Busca todos os arquivos .docx e Google Docs na pasta
        query = (
            f"('{folder_id}' in parents) and "
            "("
            "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' or "
            "mimeType='application/vnd.google-apps.document'"
            ") and trashed=false"
        )
        files = []
        page_token = None
        while True:
            response = service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType)',
                pageToken=page_token
            ).execute()
            files.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)
            if page_token is None:
                break

        if not files:
            flash('Nenhum arquivo .docx ou Google Docs encontrado na pasta.', 'warning')
            return redirect(url_for('index'))

        print(f"convert_folder: {len(files)} arquivos encontrados para conversão.")

        # Processa cada arquivo
        for file in files:
            file_id = file['id']
            filename = file['name']
            mime_type = file.get('mimeType')
            print(f"convert_folder: Processando {filename} ({file_id}) tipo {mime_type}")

            # Download conforme o tipo
            if mime_type == 'application/vnd.google-apps.document':
                # Google Docs: exporta como docx
                request = service.files().export_media(
                    fileId=file_id,
                    mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
                file_content = request.execute()
            else:
                # .docx enviado: baixa direto
                request = service.files().get_media(fileId=file_id)
                file_content = request.execute()

            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            # Extrai markdown e converte
            markdown_text = converter.extract_text_from_docx(temp_file_path)
            doc_bytes = converter.parse_markdown_to_docx(markdown_text, '', None)
            output_filename = f"{os.path.splitext(filename)[0]}_formatado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            # Salva convertido temporariamente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as temp_out:
                temp_out.write(doc_bytes.read())
                temp_out_path = temp_out.name
            # Upload para a mesma pasta
            with open(temp_out_path, 'rb') as f:
                file_data = f.read()
            media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document', resumable=False)
            uploaded = service.files().create(
                body={
                    'name': output_filename,
                    'mimeType': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'parents': [folder_id]
                },
                media_body=media,
                fields='id,webViewLink'
            ).execute()
            print(f"convert_folder: Arquivo convertido enviado: {uploaded.get('webViewLink')}")
            os.unlink(temp_file_path)
            os.unlink(temp_out_path)

        flash(f'{len(files)} arquivos convertidos e enviados para a mesma pasta no Google Drive!', 'success')
        return redirect(url_for('index'))
    except HttpError as e:
        print(f"convert_folder: HttpError {e.resp.status} - {e}")
        flash(f'Erro do Google Drive: {str(e)}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"convert_folder: Erro durante a conversão em lote: {str(e)}")
        flash(f'Erro durante a conversão em lote: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    """Remove as credenciais da sessão"""
    if 'credentials' in session:
        del session['credentials']
    flash('Logout realizado com sucesso.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)