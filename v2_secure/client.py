# client.py
# Client TCP sécurisé par TLS (V2)
# Le protocole applicatif (JSON, LOGIN, MSG, FILE, etc.) est identique à la V1.
# Seule la couche de transport change : TCP -> TLS.

import ssl          # Module TLS (sécurisation de la connexion)
import socket       # Module réseau TCP
import time         # Pour les timestamps
import secrets      # Pour générer des nonces uniques
import os           # Pour la gestion des fichiers
from common import send_json, recv_json  # Fonctions communes (inchangées)


# -------------------------------------------------------------------
# Création du contexte TLS CLIENT
# -------------------------------------------------------------------
# On définit ici la CA de confiance.
# Le client n'acceptera QUE les certificats signés par cette CA.
context = ssl.create_default_context(
    cafile="../certs/rootCA.crt"  # Chemin vers le certificat de la Root CA
)


def send_file(sock, sock_file, path, username):
    """
    Envoie un fichier au serveur via la connexion TLS.
    Le fichier est lu en clair (chiffrement assuré par TLS).
    """

    # Lecture du fichier à envoyer
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Construction du message FILE
    msg = {
        "type": "FILE",
        "username": username,
        "filename": os.path.basename(path),
        "payload": content,
        "timestamp": time.time(),
        "nonce": secrets.token_hex(8)
    }

    print(f"[>] Envoi du fichier {path} au serveur")
    send_json(sock, msg)

    # Réception de l'accusé de réception
    response = recv_json(sock_file)
    print(f"[<] Réponse du serveur: {response}")


def main():
    # ----------------------------------------------------------------
    # Récupération des paramètres utilisateur
    # ----------------------------------------------------------------

    host = input("Adresse IP du serveur [127.0.0.1] : ").strip() or "127.0.0.1"
    port = int(input("Port du serveur [5000] : ").strip() or 5000)
    username = input("Nom d'utilisateur [alice] : ").strip() or "alice"

    file_path = input(
        "Chemin du fichier à envoyer (ou vide pour ne pas envoyer de fichier) : "
    ).strip() or None

    # ----------------------------------------------------------------
    # Création de la socket TCP brute
    # ----------------------------------------------------------------
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # ----------------------------------------------------------------
    # Encapsulation TLS de la socket TCP
    # ----------------------------------------------------------------
    # wrap_socket :
    # - déclenche le handshake TLS
    # - vérifie le certificat serveur
    # - vérifie le SAN (IP / DNS)
    tls_sock = context.wrap_socket(
        raw_sock,
        server_hostname=host  # IMPORTANT : utilisé pour vérifier le SAN
    )

    print(f"[*] Connexion TLS à {host}:{port} ...")
    tls_sock.connect((host, port))
    print(f"[*] Connecté en TLS au serveur {host}:{port}\n")

    # ----------------------------------------------------------------
    # Création d'un flux de lecture ligne-par-ligne
    # ----------------------------------------------------------------
    # recv_json() utilise readline(), donc on crée un objet fichier UNE FOIS.
    sock_file = tls_sock.makefile("r", encoding="utf-8", newline="\n")

    # ----------------------------------------------------------------
    # LOGIN
    # ----------------------------------------------------------------
    login = {
        "type": "LOGIN",
        "username": username,
        "password": "password123",  # toujours en clair côté applicatif
        "timestamp": time.time(),
        "nonce": secrets.token_hex(8)
    }

    print("[>] Envoi LOGIN :", login)
    send_json(tls_sock, login)

    resp = recv_json(sock_file)
    print("[<] Réponse LOGIN :", resp, "\n")

    # ----------------------------------------------------------------
    # MSG
    # ----------------------------------------------------------------
    messages = [
        "hello serveur",
        "test ACK",
        "vive la V2 sécurisée"
    ]

    for text in messages:
        msg = {
            "type": "MSG",
            "username": username,
            "payload": text,
            "timestamp": time.time(),
            "nonce": secrets.token_hex(8)
        }

        print("[>] Envoi MSG :", text)
        send_json(tls_sock, msg)

        resp = recv_json(sock_file)
        print("[<] Réponse MSG :", resp, "\n")
        time.sleep(0.2)

    # ----------------------------------------------------------------
    # PING / PONG
    # ----------------------------------------------------------------
    ping = {
        "type": "PING",
        "timestamp": time.time()
    }

    print("[>] Envoi PING")
    send_json(tls_sock, ping)

    resp = recv_json(sock_file)
    print("[<] Réponse PING :", resp, "\n")

    # ----------------------------------------------------------------
    # FILE
    # ----------------------------------------------------------------
    if file_path:
        if os.path.exists(file_path):
            send_file(tls_sock, sock_file, file_path, username)
        else:
            print(f"[!] Fichier '{file_path}' introuvable, pas d'envoi FILE.\n")

    # ----------------------------------------------------------------
    # TYPE INCONNU (test d'erreur)
    # ----------------------------------------------------------------
    bad = {
        "type": "WTF",
        "payload": "ce type n'existe pas"
    }

    print("[>] Envoi type inconnu :", bad)
    send_json(tls_sock, bad)

    resp = recv_json(sock_file)
    print("[<] Réponse ERR :", resp)

    # ----------------------------------------------------------------
    # Fermeture propre
    # ----------------------------------------------------------------
    sock_file.close()
    tls_sock.close()


if __name__ == "__main__":
    main()
