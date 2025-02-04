import socket
import ssl
import os
from pyicloud import PyiCloudService
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

ICLOUD_EMAIL = os.getenv("ICLOUD_EMAIL")
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 5105))
SERVER_CERT_PATH = os.getenv("SERVER_CERT_PATH", "credentials/server.crt")
SERVER_KEY_PATH = os.getenv("SERVER_KEY_PATH", "credentials/server.key")
COOKIE_DIRECTORY = os.getenv("COOKIE_DIRECTORY", "credentials/cookies")
BACKUP_FOLDER_NAME = os.getenv("BACKUP_FOLDER_NAME", "Backups")


def init_icloud():
    global icloud
    icloud = PyiCloudService(ICLOUD_EMAIL, cookie_directory=COOKIE_DIRECTORY)
    icloud.drive.params["clientId"] = icloud.client_id  # maybe fix...


init_icloud()

if icloud.requires_2fa:
    print("Two-factor authentication required.")
    code = input("Enter the code you received of one of your approved devices: ")
    result = icloud.validate_2fa_code(code)
    print("Code validation result: %s" % result)

    if not result:
        print("Failed to verify security code")
        exit(1)

    if not icloud.is_trusted_session:
        print("Session is not trusted. Requesting trust...")
        result = icloud.trust_session()
        print("Session trust result %s" % result)

        if not result:
            print("Failed to request trust. You will likely be prompted for the code again in the coming weeks")


class BackupServer:
    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.server_address = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile=SERVER_CERT_PATH, keyfile=SERVER_KEY_PATH)

        self.sock.bind(self.server_address)
        self.sock.listen(5)
        print(f"[SERVER] Listening on {host}:{port}")

    def handle_client(self, connection, address):
        print(f"[SERVER] Connection established with {address}")
    
        with self.context.wrap_socket(connection, server_side=True) as ssock:
            metadata_size = int.from_bytes(ssock.recv(4), 'big')
            metadata = ssock.recv(metadata_size).decode()
            total_chunks, chunk_size, file_size = map(int, metadata.split(','))
            
            print(f"[SERVER] Expecting {total_chunks} chunks of {chunk_size} bytes, total {file_size} bytes")
            
            ssock.send(b'OK')
    
            _address = address[0].replace('.', '_')
            filename = f"backup_{file_size}.zip"
            
            with open(filename, "wb") as f:  # TODO: в будущем можно повторно запрашивать потерянные чанки
                chunks_received = 0
                bytes_received = 0
                
                while bytes_received < file_size:
                    remaining = min(chunk_size, file_size - bytes_received)
                    chunk = ssock.recv(remaining)
                    if not chunk:
                        break
                        
                    f.write(chunk)
                    bytes_received += len(chunk)
                    chunks_received += 1
                    print(f"[SERVER] Received chunk {chunks_received}/{total_chunks}")
            
            connection.close()
            if bytes_received == file_size:
                print(f"[SERVER] Data saved to {filename}: {bytes_received} bytes")
                self.upload_to_icloud(filename, _address)
            else:
                print(f"[SERVER] Transfer incomplete. Received {bytes_received}/{file_size} bytes")

            os.remove(filename)

    def upload_to_icloud(self, filename, _address):
        try:
            if BACKUP_FOLDER_NAME not in icloud.drive.dir():
                icloud.drive.mkdir(BACKUP_FOLDER_NAME)
                print(f"[SERVER] '{BACKUP_FOLDER_NAME}' folder created in iCloud")
                init_icloud()

            ip_folder_path = f"Backups/{_address}"
            if _address not in icloud.drive["Backups"].dir():
                icloud.drive["Backups"].mkdir(_address)
                print(f"[SERVER] '{_address}' folder created in iCloud")
                init_icloud()

            current_date = datetime.now().strftime("%d-%m-%Y")
            date_folder_path = f"{ip_folder_path}/{current_date}"
            if current_date not in icloud.drive["Backups"][_address].dir():
                icloud.drive["Backups"][_address].mkdir(current_date)
                print(f"[SERVER] '{current_date}' folder created in iCloud under '{_address}'")
                init_icloud()

            with open(filename, "rb") as file:
                icloud.drive["Backups"][_address][current_date].upload(file)
            print(f"[SERVER] {filename} uploaded to iCloud in '{date_folder_path}'")
        except Exception as e:
            print(f"[SERVER] iCloud upload failed: {e}")

    def run(self):
        while True:
            connection, address = self.sock.accept()
            self.handle_client(connection, address)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup Server")
    parser.add_argument("--host", default=SERVER_HOST, help=f"Server host (default: {SERVER_HOST})")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"Server port (default: {SERVER_PORT})")

    args = parser.parse_args()

    server = BackupServer(host=args.host, port=args.port)
    server.run()
