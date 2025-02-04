import socket
import os
import zipfile
import ssl

try:
    from dotenv import load_dotenv
    
    load_dotenv()
except ImportError:
    print("[CLIENT] Warning: python-dotenv not found, using default values")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 4096))
SERVER_HOST = os.getenv("SERVER_HOST", "example.domain.com")
SERVER_CERT_PATH = os.getenv("SERVER_CERT_PATH", "credentials/server.crt")
SERVER_PORT = int(os.getenv("SERVER_PORT", 5105))


class BackupClient:
    def __init__(self, server_host, server_port, path_to_backup, cert_file):
        self.server_address = (socket.gethostbyname(server_host), server_port)
        self.path_to_backup = path_to_backup
        self.cert_file = cert_file

    def backup(self):
        zip_filename = "backup.zip"
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            if os.path.isfile(self.path_to_backup):
                zipf.write(self.path_to_backup, os.path.basename(self.path_to_backup))
                print(f"[CLIENT] Adding file to archive: {self.path_to_backup}")
            elif os.path.isdir(self.path_to_backup):
                for root, dirs, files in os.walk(self.path_to_backup):
                    for file in files:
                        filepath = os.path.join(root, file)
                        if os.path.isfile(filepath):
                            arcname = os.path.relpath(filepath, self.path_to_backup)
                            zipf.write(filepath, arcname)
                            print(f"[CLIENT] Adding to archive: {arcname}")
                        else:
                            print(f"[CLIENT] Skipping non-regular file: {filepath}")
            else:
                print(f"[CLIENT] Error: {self.path_to_backup} is neither a file nor a directory")
                return
    
        file_size = os.path.getsize(zip_filename)
        chunk_size = CHUNK_SIZE
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        print(f"[CLIENT] Path {self.path_to_backup} archived to {zip_filename}: {file_size} bytes")
        print(f"[CLIENT] Will send {total_chunks} chunks of {chunk_size} bytes")
        
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.cert_file)
    
        with socket.create_connection(self.server_address) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname=self.server_address[0]) as sock:
                metadata = f"{total_chunks},{chunk_size},{file_size}".encode()
                sock.send(len(metadata).to_bytes(4, 'big'))
                sock.send(metadata)
                
                if sock.recv(2) != b'OK':
                    print("[CLIENT] Server did not acknowledge metadata")
                    return
    
                with open(zip_filename, "rb") as f:
                    chunks_sent = 0
                    while chunk := f.read(chunk_size):
                        sock.sendall(chunk)
                        chunks_sent += 1
                        print(f"[CLIENT] Sent chunk {chunks_sent}/{total_chunks}")
    
                print(f"[CLIENT] Data sent securely to {self.server_address}")
    
        os.remove(zip_filename)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backup Client")
    parser.add_argument("--host", default=SERVER_HOST, help=f"Server host (e.g., {SERVER_HOST})")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"Server port (default: {SERVER_PORT})")
    parser.add_argument("--path", help="File or folder to backup")
    parser.add_argument("--cert", default=SERVER_CERT_PATH, help=f"Path to server certificate (default: {SERVER_CERT_PATH})")
    
    args = parser.parse_args()

    client = BackupClient(args.host, args.port, args.path, args.cert)
    client.backup()
