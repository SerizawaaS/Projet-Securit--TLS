# server.py
# Serveur TCP sécurisé par TLS (V2)
# Le protocole applicatif (JSON : LOGIN, MSG, FILE, PING) est identique à la V1.
# On remplace simplement la couche TCP brute par une couche TLS.
#
# Objectifs TLS:
# - Chiffrement des échanges (confidentialité)
# - Intégrité (détection modification)
# - Authentification du serveur (certificat signé par la CA)

import ssl         # module ssl pour activer TLS côté serveur
import socket      # module socket pour la communication réseau TCP
import threading   # gestion de plusieurs clients en parallèle
import time        # timestamps côté serveur
import os          # gestion des chemins/dossiers pour stocker les fichiers
from common import send_json, recv_json  # fonctions JSON (inchangées)

HOST = "0.0.0.0"   # écoute sur toutes les interfaces (LAN + localhost)
PORT = 5000        # port applicatif

# Dossier où on stocke les fichiers reçus (optionnel mais propre)
RECEIVE_DIR = "received_files"


def handle_client(conn, addr):
    """
    Gère un client (dans un thread).
    IMPORTANT : ici conn est une socket TLS (ssl.SSLSocket), pas une socket TCP brute.
    """
    print(f"[+] Client connecté: {addr}")

    # On crée un flux de lecture ligne-par-ligne UNE FOIS.
    # readline() = 1 message JSON (terminé par \n) dans notre protocole.
    sock_file = conn.makefile("r", encoding="utf-8", newline="\n")

    try:
        while True:
            # Réception d'un message JSON
            msg = recv_json(sock_file)

            # None = connexion fermée par le client
            if msg is None:
                print(f"[-] Client déconnecté: {addr}")
                break

            print(f"[{addr}] RECU: {msg}")
            mtype = msg.get("type")

            if mtype == "LOGIN":
                # Dans V2, le login est toujours du JSON "en clair" côté applicatif,
                # mais il est chiffré sur le réseau grâce à TLS.
                send_json(conn, {
                    "type": "OK",
                    "message": "login accepted (v2 TLS)",
                    "server_time": time.time()
                })

            elif mtype == "MSG":
                send_json(conn, {
                    "type": "ACK",
                    "echo": msg.get("payload", ""),
                    "server_time": time.time()
                })

            elif mtype == "FILE":
                filename = msg.get("filename", "received.txt")
                data = msg.get("payload", "")

                print(f"[FILE] Reçu fichier {filename} de {addr}, taille: {len(data)} octets")

                # On stocke les fichiers reçus dans un dossier dédié
                os.makedirs(RECEIVE_DIR, exist_ok=True)
                filepath = os.path.join(RECEIVE_DIR, f"receive_{filename}")

                # Ici on écrit en texte UTF-8 car payload est une chaîne
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(data)

                send_json(conn, {
                    "type": "ACK_FILE",
                    "filename": filename,
                    "size": len(data),
                    "server_time": time.time()
                })

            elif mtype == "PING":
                send_json(conn, {
                    "type": "PONG",
                    "server_time": time.time()
                })

            else:
                # Message inconnu = réponse d'erreur
                send_json(conn, {
                    "type": "ERR",
                    "message": "unknown type",
                    "server_time": time.time()
                })

    except Exception as e:
        print(f"[!] Erreur avec {addr}: {e}")

    finally:
        # Fermeture propre
        try:
            sock_file.close()
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

        print(f"[+] Connexion fermée: {addr}")


def main():
    # ----------------------------------------------------------------
    # 1) Contexte TLS serveur
    # ----------------------------------------------------------------
    # On configure TLS côté serveur et on charge:
    # - server.crt : certificat serveur (signé par la CA)
    # - server.key : clé privée du serveur
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # NOTE IMPORTANTE SUR LES CHEMINS:
    # Tu as indiqué que "certs/" est à la racine du projet (au même niveau que v2_secure/).
    # Donc depuis v2_secure/, le chemin est "../certs/..."
    context.load_cert_chain(
        certfile="../certs/server.crt",
        keyfile="../certs/server.key"
    )

    # ----------------------------------------------------------------
    # 2) Socket TCP en écoute
    # ----------------------------------------------------------------
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)

        print(f"[*] Serveur TLS en écoute sur {HOST}:{PORT}")

        # ----------------------------------------------------------------
        # 3) Accepter des connexions et les "wrapper" en TLS
        # ----------------------------------------------------------------
        while True:
            conn, addr = s.accept()
            print(f"[+] Nouvelle connexion TCP de {addr}")

            # IMPORTANT: wrap_socket transforme la connexion TCP en connexion TLS
            # Le handshake TLS se fait ici.
            tls_conn = context.wrap_socket(conn, server_side=True)
            print(f"[+] Connexion TLS établie avec {addr}")

            # IMPORTANT: on passe tls_conn au thread, pas conn
            threading.Thread(
                target=handle_client,
                args=(tls_conn, addr),
                daemon=True
            ).start()


if __name__ == "__main__":
    main()
