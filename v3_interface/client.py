# client_network.py
# Couche réseau TLS (pas d'UI ici).
# Envoie/recevra JSON via TLS et expose des méthodes propres pour l'interface.

import ssl
import socket
import threading
import time
import secrets
import os

from common import send_json, recv_json


class SecureClient:
    def __init__(self, host, port, username, log_callback):
        self.host = host
        self.port = port
        self.username = username
        self.log = log_callback

        self.sock = None
        self.sock_file = None

        # CA de confiance (dans v3_interface, rootCA.crt est dans le même dossier que ce script)
        self.context = ssl.create_default_context(cafile="rootCA.crt")

    def connect(self):
        # 1) socket TCP brute
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 2) encapsulation TLS + vérification SAN/cert
        self.sock = self.context.wrap_socket(
            raw_sock,
            server_hostname=self.host
        )

        # 3) connexion (TCP + handshake TLS)
        self.sock.connect((self.host, self.port))

        # 4) flux de lecture ligne-par-ligne
        self.sock_file = self.sock.makefile("r", encoding="utf-8", newline="\n")

        # 5) LOGIN
        login = {
            "type": "LOGIN",
            "username": self.username,
            "password": "password123",
            "timestamp": time.time(),
            "nonce": secrets.token_hex(8)
        }
        send_json(self.sock, login)

        # 6) thread réception
        threading.Thread(target=self.listen_loop, daemon=True).start()

    def listen_loop(self):
        while True:
            msg = recv_json(self.sock_file)
            if msg is None:
                self.log("[!] Déconnecté du serveur")
                break

            mtype = msg.get("type")

            if mtype == "MSG":
                # message chat relayé par le serveur
                frm = msg.get("from", "unknown")
                frm_ip = msg.get("from_ip", "?")
                payload = msg.get("payload", "")
                self.log(f"[{frm}@{frm_ip}] {payload}")

            elif mtype == "FILE_FROM":
                # fichier relayé par le serveur (si tu utilises to_ip sur FILE)
                frm = msg.get("from", "unknown")
                frm_ip = msg.get("from_ip", "?")
                filename = msg.get("filename", "file.txt")
                content = msg.get("payload", "")

                # on sauvegarde localement
                outname = f"received_{filename}"
                with open(outname, "w", encoding="utf-8") as f:
                    f.write(content)

                self.log(f"[FILE] reçu de {frm}@{frm_ip} -> {outname}")

            elif mtype in ("ACK", "ACK_FILE", "OK", "ERR", "PONG"):
                self.log(f"[SERVEUR] {msg}")

            else:
                self.log(f"[SERVEUR] {msg}")

    def send_message(self, text, to_ip="*"):
        msg = {
            "type": "MSG",
            "username": self.username,
            "to_ip": to_ip,  # "*" ou IP précise
            "payload": text,
            "timestamp": time.time(),
            "nonce": secrets.token_hex(8)
        }
        send_json(self.sock, msg)

    def send_file(self, path, to_ip="*"):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        msg = {
            "type": "FILE",
            "username": self.username,
            "to_ip": to_ip,  # "*" = stockage serveur, IP = relai vers client(s)
            "filename": os.path.basename(path),
            "payload": content,
            "timestamp": time.time(),
            "nonce": secrets.token_hex(8)
        }
        send_json(self.sock, msg)
