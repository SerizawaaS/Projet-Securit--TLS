# client.py
# Ce fichier permet de créer un client TCP simple qui se connecte au serveur
# et envoie des messages. On retrouve les mêmes types de messages que côté serveur
# (LOGIN, MSG, FILE, PING, ERR).

import socket   # pour créer la connexion TCP
import time     # pour les temporisations / timestamps
import secrets  # pour créer un nonce unique
import os       # pour les opérations sur les fichiers
from common import send_json, recv_json  # import des fonctions communes


def send_file(sock, sock_file, path, username):
    """
    Cette fonction sert à envoyer un fichier en clair au serveur.
    IMPORTANT (nouvelle version): recv_json() attend sock_file (flux), pas sock (socket).
    """

    # On ouvre le fichier en mode lecture texte (V1 = en clair)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # On construit le message JSON pour envoyer le fichier
    msg = {
        "type": "FILE",
        "username": username,
        # os.path.basename récupère uniquement le nom du fichier à partir du chemin complet
        "filename": os.path.basename(path),
        # payload contient le contenu du fichier (en clair en V1)
        "payload": content,
        # time.time() retourne le temps écoulé depuis le 1er janvier 1970 (timestamp Unix)
        "timestamp": time.time(),
        # nonce unique pour chaque message (utile pour démontrer replay en V1)
        "nonce": secrets.token_hex(8)
    }

    print(f"[>] Envoi du fichier {path} au serveur")
    send_json(sock, msg)

    # On lit la réponse du serveur via sock_file (lecture ligne par ligne)
    response = recv_json(sock_file)
    print(f"[<] Réponse du serveur: {response}")


def main():
    # ---- On demande les infos à l'utilisateur (valeurs par défaut) ----

    # Adresse IP du serveur (par défaut 127.0.0.1)
    host_input = input("Adresse IP du serveur [127.0.0.1] : ").strip()
    if host_input == "":
        host = "127.0.0.1"
    else:
        host = host_input

    # Port du serveur (par défaut 5000)
    port_input = input("Port du serveur [5000] : ").strip()
    if port_input == "":
        port = 5000
    else:
        port = int(port_input)

    # Nom d'utilisateur (username)
    username_input = input("Nom d'utilisateur [alice] : ").strip()
    if username_input == "":
        username = "alice"
    else:
        username = username_input

    # Fichier à envoyer (optionnel)
    file_path = input("Chemin du fichier à envoyer (ou vide pour ne pas envoyer de fichier) : ").strip()
    if file_path == "":
        file_path = None

    # Création du socket TCP client
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        # Connexion au serveur
        print(f"[*] Connexion à {host}:{port} ...")
        s.connect((host, port))
        print(f"[*] Connecté au serveur {host}:{port}\n")

        # IMPORTANT (nouvelle version):
        # On crée UNE FOIS un flux de lecture ligne-par-ligne associé à la socket.
        # Cela permet à recv_json() d'utiliser readline() et de lire exactement 1 message (1 ligne) à la fois.
        sock_file = s.makefile("r", encoding="utf-8", newline="\n")

        # ----------- LOGIN -----------
        login = {
            "type": "LOGIN",
            "username": username,
            "password": "password123",  # toujours en clair en V1
            "timestamp": time.time(),
            "nonce": secrets.token_hex(8)
        }
        print("[>] Envoi LOGIN :", login)
        send_json(s, login)

        # Réception réponse LOGIN (via sock_file, pas via la socket)
        resp = recv_json(sock_file)
        print("[<] Réponse LOGIN :", resp, "\n")

        # ----------- MSG -----------
        messages = [
            "hello serveur",
            "test ACK",
            "vive la V1 non sécurisée"
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
            send_json(s, msg)

            # Réception réponse MSG (via sock_file)
            resp = recv_json(sock_file)
            print("[<] Réponse MSG :", resp, "\n")

            # Petite temporisation pour lisibilité
            time.sleep(0.2)

        # ----------- PING / PONG -----------
        ping = {
            "type": "PING",
            "timestamp": time.time()
        }
        print("[>] Envoi PING")
        send_json(s, ping)

        resp = recv_json(sock_file)
        print("[<] Réponse PING :", resp, "\n")

        # ----------- FILE (si demandé) -----------
        if file_path is not None:
            if os.path.exists(file_path):
                send_file(s, sock_file, file_path, username=username)
            else:
                print(f"[!] Fichier '{file_path}' introuvable, pas d'envoi FILE.\n")

        # ----------- TYPE INCONNU -----------
        bad = {
            "type": "WTF",
            "payload": "ce type n'existe pas"
        }
        print("[>] Envoi type inconnu :", bad)
        send_json(s, bad)

        resp = recv_json(sock_file)
        print("[<] Réponse ERR :", resp)

        # Fermeture propre du flux
        try:
            sock_file.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
