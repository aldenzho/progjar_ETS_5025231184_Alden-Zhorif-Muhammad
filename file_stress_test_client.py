import base64
import time
import os
import json
import socket
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

server_address = ("172.18.0.3", 60001)  # ganti IP jika server remote

def send_command(command_str):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(server_address)
        sock.sendall(command_str.encode())
        data_received = ""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            data_received += data.decode()
            if "\r\n\r\n" in data_received:
                break
        sock.close()
        return True, json.loads(data_received)
    except Exception as e:
        return False, str(e)

def encode_file_to_base64(file_path):
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    return encoded

def list_files():
    request_str = "LIST\r\n\r\n"
    success, result = send_command(request_str)

    if success and isinstance(result, dict) and result.get("status") == "OK":
        print("Files on server (folder progjarETS):")
        for fname in result.get("data", []):
            print(f" - {fname}")
        return {
            "success": True,
            "files": result.get("data", []),
            "error": None
        }
    else:
        print("Failed to retrieve file list:", result)
        return {
            "success": False,
            "files": [],
            "error": result
             }

def upload_file(filename):
    filepath = filename
    file_content = encode_file_to_base64(filepath)
    server_file_path = os.path.join("progjarETS", os.path.basename(filepath))

    request = {
        "command": "upload",
        "file_name": server_file_path,
        "file_content": file_content
    }
    request_str = json.dumps(request) + "\r\n\r\n"

    start = time.time()
    success, result = send_command(request_str)
    end = time.time()

    return {
        "success": success,
        "duration": end - start,
        "filesize": os.path.getsize(filepath),
        "error": None if success else result
    }

def download_file(filename):
    local_folder = "progjarETS"
    os.makedirs(local_folder, exist_ok=True)

    request = {
        "command": "download",
        "file_name": filename
    }
    request_str = json.dumps(request) + "\r\n\r\n"

    start = time.time()
    success, result = send_command(request_str)
    end = time.time()

    if success and result.get("status") == "OK":
        file_bytes = base64.b64decode(result["file_content"])
        # Simpan di folder progjarETS dengan nama file asli
        local_path = os.path.join(local_folder, os.path.basename(filename))
        with open(local_path, "wb") as f:
            f.write(file_bytes)
            return {
            "success": True,
            "duration": end - start,
            "filesize": len(file_bytes),
            "error": None
        }
    else:
        return {
            "success": False,
            "duration": end - start,
            "filesize": 0,
            "error": result
        }

def delete_file(filename):
    server_file_path = os.path.join("progjarETS", os.path.basename(filename))
    request = {
        "command": "delete",
        "file_name": server_file_path
    }
    request_str = json.dumps(request) + "\r\n\r\n"

    success, result = send_command(request_str)

    if success and result.get("status") == "OK":
        return {
            "success": True,
            "message": result.get("data")
        }
    else:
        return {
            "success": False,
            "error": result
        }
def stress_test(operation, filename, pool_type="thread", client_workers=1):
    print(f"Running {operation} stress test | Pool: {pool_type} | Clients: {client_workers} | File: {filename}")
    target_func = upload_file if operation == "upload" else download_file
    results = []
    executor_class = ThreadPoolExecutor if pool_type == "thread" else ProcessPoolExecutor

    with executor_class(max_workers=client_workers) as executor:
        futures = [executor.submit(target_func, filename) for _ in range(client_workers)]
        for f in futures:
            results.append(f.result())

    total_duration = sum([r["duration"] for r in results])
    avg_duration = total_duration / len(results)
    total_bytes = sum([r["filesize"] for r in results])
    throughput_per_client = [r["filesize"] / r["duration"] for r in results if r["success"]]

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    print(f"Total clients: {len(results)}")
    print(f"Success: {success_count}, Fail: {fail_count}")
    print(f"Average Duration per client: {avg_duration:.2f} seconds")
    print(f"Average Throughput per client: {sum(throughput_per_client)/len(throughput_per_client):.2f} B/s" if throughput_per_client else "Throughput N/A")

    return {
        "success": success_count,
        "fail": fail_count,
        "avg_duration": avg_duration,
        "avg_throughput": sum(throughput_per_client)/len(throughput_per_client) if throughput_per_client else 0
    }

# uncomment sesuai test yang ingin dijalankan
if __name__ == "__main__":
    list_files()
    # delete_file()
    # stress_test("upload", "file_50MB.dat", pool_type="thread", client_workers=50)
    # stress_test("download", "file_10MB.dat", pool_type="thread", client_workers=1)