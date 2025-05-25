import argparse
import socket
import logging
import json
import os
import base64
import concurrent.futures
import signal
import sys

HOST = '0.0.0.0'
PORT = 60001
UPLOAD_FOLDER = "progjarETS"
BUFFER_SIZE = 4096


def save_file_stream(file_name, chunk_generator):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    full_path = os.path.join(UPLOAD_FOLDER, file_name)

    with open(full_path, "wb") as f:
        leftover = ""

        for chunk in chunk_generator:
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")

            chunk = leftover + chunk
            valid_len = (len(chunk) // 4) * 4
            if valid_len == 0:
                leftover = chunk
                continue

            to_decode = chunk[:valid_len]
            leftover = chunk[valid_len:]

            try:
                f.write(base64.b64decode(to_decode))
            except Exception as e:
                logging.error(f"Base64 decode error: {e}")
                raise e

        if leftover:
            try:
                f.write(base64.b64decode(leftover))
            except Exception as e:
                logging.error(f"Final base64 decode error: {e}")
                raise e
def handle_client(conn, addr):
    logging.info(f"Connected by {addr}")
    conn.settimeout(30)  
    data_buffer = ""

    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break
            data_buffer += data.decode(errors="ignore")

            if "\r\n\r\n" in data_buffer:
                request_str, _, remainder = data_buffer.partition("\r\n\r\n")
                data_buffer = remainder

                try:
                    request_json = json.loads(request_str)
                    cmd = request_json.get("command", "").lower()
                except Exception:
                    cmd = request_str.strip().lower()
                    if cmd == "list":
                        try:
                            files = []
                            if os.path.exists(UPLOAD_FOLDER):
                                files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f))]
                            resp = json.dumps({"status": "OK", "data": files})
                        except Exception as e:
                            resp = json.dumps({"status": "ERROR", "data": str(e)})
                        conn.sendall((resp + "\r\n\r\n").encode())
                        continue
                    else:
                        resp = json.dumps({"status": "ERROR", "data": "Invalid or unsupported command"})
                        conn.sendall((resp + "\r\n\r\n").encode())
                        continue

                if cmd == "upload":
                    file_name = request_json.get("file_name")
                    file_content_b64_start = request_json.get("file_content", "")
                    conn.sendall(json.dumps({"status": "READY"}).encode() + b"\r\n\r\n")

                    def base64_generator():
                        if file_content_b64_start:
                            yield file_content_b64_start

                        while True:
                            try:
                                chunk = conn.recv(BUFFER_SIZE)
                                if not chunk:
                                    break
                                chunk_str = chunk.decode(errors="ignore")
                                if "\r\n\r\n" in chunk_str:
                                    part, _, _ = chunk_str.partition("\r\n\r\n")
                                    yield part
                                    break
                                else:
                                    yield chunk_str
                            except socket.timeout:
                                logging.warning(f"Timeout saat upload base64 dari {addr}")
                                break

                    try:
                        save_file_stream(file_name, base64_generator())
                        resp = json.dumps({"status": "OK", "data": f"Uploaded to {file_name}"})
                    except Exception as e:
                        resp = json.dumps({"status": "ERROR", "data": str(e)})

                    conn.sendall((resp + "\r\n\r\n").encode())

                elif cmd == "download":
                    file_name = request_json.get("file_name")
                    full_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file_name))
                    try:
                        with open(full_path, "rb") as f:
                            file_bytes = f.read()
                        file_b64 = base64.b64encode(file_bytes).decode()
                        resp = json.dumps({"status": "OK", "file_content": file_b64})
                    except Exception as e:
                        resp = json.dumps({"status": "ERROR", "data": str(e)})

                    conn.sendall((resp + "\r\n\r\n").encode())

                elif cmd == "delete":
                    file_name = request_json.get("file_name")
                    try:
                        full_path = os.path.join(UPLOAD_FOLDER, os.path.basename(file_name))
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            os.remove(full_path)
                            resp = json.dumps({"status": "OK", "data": f"Deleted {file_name}"})
                        else:
                            resp = json.dumps({"status": "ERROR", "data": "File not found"})
                    except Exception as e:
                        resp = json.dumps({"status": "ERROR", "data": str(e)})

                    conn.sendall((resp + "\r\n\r\n").encode())

                else:
                    resp = json.dumps({"status": "ERROR", "data": "Unknown command"})
                    conn.sendall((resp + "\r\n\r\n").encode())

        conn.close()
        logging.info(f"Connection closed by {addr}")

    except socket.timeout:
        logging.warning(f"Connection timeout from {addr}")
        conn.close()
    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
        conn.close()


def run_server_threadpool(max_workers):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        logging.info(f"Server listening on {HOST}:{PORT} with thread pool max_workers={max_workers}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                while True:
                    conn, addr = s.accept()
                    executor.submit(handle_client, conn, addr)
            except KeyboardInterrupt:
                logging.info("Server shutting down (threadpool mode)")



def handle_client_process(conn_fd, addr):
    conn = socket.socket(fileno=conn_fd)
    handle_client(conn, addr)
    conn.close()

def run_server_processpool(max_workers):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        logging.info(f"Server listening on {HOST}:{PORT} with process pool max_workers={max_workers}")

        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            try:
                while True:
                    conn, addr = s.accept()
                    conn_fd = conn.fileno()
                    conn.detach() 
                    executor.submit(handle_client_process, conn_fd, addr)
            except KeyboardInterrupt:
                logging.info("Server shutting down (processpool mode)")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    parser = argparse.ArgumentParser(description="File Server with configurable max workers")
    parser.add_argument("--workers", type=int, default=10, help="Maximum number of workers (threads/processes)")
    parser.add_argument("--mode", choices=["thread", "process"], default="thread", help="Run mode: thread or process")
    args = parser.parse_args()

    max_workers = args.workers

    if args.mode == "thread":
        run_server_threadpool(max_workers)
    else:
        run_server_processpool(max_workers)

if __name__ == "__main__":
    main()
                                                                                                                                                                                                                                                  
