import tempfile

def process_drive_file(service, file_id):
    # Baixa o arquivo do Google Drive como .docx e retorna caminho e nome
    request = service.files().get_media(fileId=file_id)
    fh = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
    downloader = None
    try:
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.close()
        # Recupera nome do arquivo
        file_metadata = service.files().get(fileId=file_id).execute()
        filename = file_metadata.get('name', 'documento.docx')
        return fh.name, filename
    except Exception as e:
        if fh:
            fh.close()
        raise e
