# server.py
# Serveur TLS + routage par IP.
# - MSG: broadcast ("to_ip":"*") ou ciblé ("to_ip":"10.192.57.xxx")
# - FILE: par défaut stocké côté serveur, optionnellement relayé à une IP

import ssl
import socket
import threading
import time
import os

from common import send_json, recv_json

HOST = "0.0.0.0"
PORT = 5000

RECEIVE_DIR = "received_files"

# Table des clients connectés: ip -> liste de connexions TLS
clients_by_ip = {}
clients_lock = threading.Lock()


def register_client(conn, addr):
    """Ajoute un client dans la table."""
    ip = addr[0]
    with clients_lock:
        clients_by_ip.setdefault(ip, []).append(conn)


def unregister_client(conn, addr):
    """Retire un client de la table."""
    ip = addr[0]
    with clients_lock:
        lst = clients_by_ip.get(ip, [])
        lst = [c for c in lst if c is not conn]
        if lst:
            clients_by_ip[ip] = lst
        else:
            clients_by_ip.pop(ip, None)


def broadcast(payload, exclude_conn=None):
    """Envoie payload à tous les clients."""
    with clients_lock:
        for ip, conns in list(clients_by_ip.items()):
            for c in list(conns):
                if exclude_conn is not None and c is exclude_conn:
                    continue
                try:
                    send_json(c, payload)
                except Exception:
                    # client mort, on ignore ici (le cleanup arrivera à la déconnexion)
                    pass


def send_to_ip(target_ip, payload):
    """Envoie payload à tous les clients enregistrés sur target_ip. Retourne True si au moins 1 envoi."""
    sent = False
    with clients_lock:
        conns = clients_by_ip.get(target_ip, [])
        for c in list(conns):
            try:
                send_json(c, payload)
                sent = True
            except Exception:
                pass
    return sent


def handle_client(conn, addr):
    """
    Thread par client.
    conn est une socket TLS (ssl.SSLSocket).
    """
    print(f"[+] Client connecté: {addr}")

    # Flux lecture ligne-par-ligne (1 JSON par ligne)
    sock_file = conn.makefile("r", encoding="utf-8", newline="\n")

    try:
        while True:
            msg = recv_json(sock_file)
            if msg is None:
                print(f"[-] Client déconnecté: {addr}")
                break

            mtype = msg.get("type")
            print(f"[{addr}] RECU: {msg}")

            if mtype == "LOGIN":
                # Ici on “accepte” sans vérifier (tu peux ajouter une vraie vérif plus tard)
                send_json(conn, {
                    "type": "OK",
                    "message": "login accepted (v2 TLS + routing)",
                    "server_time": time.time()
                })

            elif mtype == "MSG":
                from_user = msg.get("username", "unknown")
                payload_text = msg.get("payload", "")
                to_ip = msg.get("to_ip", "*")  # "*" = broadcast

                outgoing = {
                    "type": "MSG",
                    "from": from_user,
                    "payload": payload_text,
                    "from_ip": addr[0],
                    "server_time": time.time()
                }

                if to_ip == "*" or to_ip == "":
                    # broadcast à tous (option: exclure l'émetteur si tu veux)
                    broadcast(outgoing, exclude_conn=None)

                    # accusé au sender (pratique UI)
                    send_json(conn, {
                        "type": "ACK",
                        "delivered_to": "*",
                        "server_time": time.time()
                    })
                else:
                    ok = send_to_ip(to_ip, outgoing)
                    if ok:
                        send_json(conn, {
                            "type": "ACK",
                            "delivered_to": to_ip,
                            "server_time": time.time()
                        })
                    else:
                        send_json(conn, {
                            "type": "ERR",
                            "message": f"unknown recipient ip: {to_ip}",
                            "server_time": time.time()
                        })

            elif mtype == "FILE":
                # Deux modes:
                # - to_ip="*" ou absent -> stocker sur le serveur
                # - to_ip="x.x.x.x" -> relayer le fichier au(x) client(s) de cette IP
                from_user = msg.get("username", "unknown")
                filename = msg.get("filename", "received.txt")
                data = msg.get("payload", "")
                to_ip = msg.get("to_ip", "*")

                if to_ip == "*" or to_ip == "":
                    print(f"[FILE] Stockage fichier {filename} de {addr}, taille: {len(data)} octets")

                    os.makedirs(RECEIVE_DIR, exist_ok=True)
                    filepath = os.path.join(RECEIVE_DIR, f"receive_{filename}")
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(data)

                    send_json(conn, {
                        "type": "ACK_FILE",
                        "mode": "stored_on_server",
                        "filename": filename,
                        "size": len(data),
                        "server_time": time.time()
                    })
                else:
                    outgoing = {
                        "type": "FILE_FROM",
                        "from": from_user,
                        "from_ip": addr[0],
                        "filename": filename,
                        "payload": data,
                        "size": len(data),
                        "server_time": time.time()
                    }

                    ok = send_to_ip(to_ip, outgoing)
                    if ok:
                        send_json(conn, {
                            "type": "ACK_FILE",
                            "mode": "relayed",
                            "to_ip": to_ip,
                            "filename": filename,
                            "size": len(data),
                            "server_time": time.time()
                        })
                    else:
                        send_json(conn, {
                            "type": "ERR",
                            "message": f"unknown recipient ip for file: {to_ip}",
                            "server_time": time.time()
                        })

            elif mtype == "PING":
                send_json(conn, {
                    "type": "PONG",
                    "server_time": time.time()
                })

            else:
                send_json(conn, {
                    "type": "ERR",
                    "message": "unknown type",
                    "server_time": time.time()
                })

    except Exception as e:
        print(f"[!] Erreur avec {addr}: {e}")

    finally:
        try:
            sock_file.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        unregister_client(conn, addr)
        print(f"[+] Connexion fermée: {addr}")


def main():
    # Contexte TLS serveur
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(
        certfile="../certs/server.crt",
        keyfile="../certs/server.key"
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        print(f"[*] Serveur TLS + routage IP en écoute sur {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            tls_conn = context.wrap_socket(conn, server_side=True)

            register_client(tls_conn, addr)
            print(f"[+] Connexion TLS établie avec {addr}")

            threading.Thread(
                target=handle_client,
                args=(tls_conn, addr),
                daemon=True
            ).start()


if __name__ == "__main__":
    main()
