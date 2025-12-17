# server.py
# Ce fichier crée un serveur TCP qui écoute les connexions entrantes
# et gère les messages reçus. Il répond selon le type de message reçu
# (LOGIN, MSG, FILE, PING).

import socket      # module socket pour la communication réseau
import threading   # threading pour gérer plusieurs clients en parallèle
import time        # time pour fournir un timestamp côté serveur
from common import send_json, recv_json  # fonctions communes d'envoi/réception JSON


HOST = "0.0.0.0"   # adresse loopback (serveur local sur la même machine) pour le second test on utilisera 0.0.0.0 
#pour écouter sur toutes les interfaces
PORT = 5000          # port d'écoute (port applicatif non privilégié)


def handle_client(conn, addr):
    """
    Fonction exécutée dans un thread pour gérer un client.
    conn : socket de connexion côté serveur
    addr : adresse (IP, port) du client
    """
    print(f"[+] Client connecté: {addr}")

    # IMPORTANT (nouvelle version):
    # On crée UNE FOIS un flux de lecture "file-like" à partir de la socket.
    # Cela permet d'utiliser readline() et de lire exactement 1 message (1 ligne) à la fois.
    sock_file = conn.makefile("r", encoding="utf-8", newline="\n")

    try:
        # Boucle infinie: on traite les messages tant que le client reste connecté
        while True:
            # recv_json attend un sock_file (pas conn) dans la nouvelle version
            msg = recv_json(sock_file)

            # Si msg est None, cela signifie que le client a fermé la connexion
            if msg is None:
                print(f"[-] Client déconnecté: {addr}")
                break

            # Log de ce qu'on reçoit (utile pour démo et rapport)
            print(f"[{addr}] RECU: {msg}")

            # Dans notre protocole JSON, le champ "type" indique l'action demandée
            mtype = msg.get("type")

            # Selon le type, le serveur répond différemment
            if mtype == "LOGIN":
                # V1 non sécurisé: pas de vraie vérification du mot de passe
                send_json(conn, {
                    "type": "OK",
                    "message": "login accepted (v1 insecure)",
                    "server_time": time.time()
                })

            elif mtype == "MSG":
                # Message classique: on renvoie un accusé de réception
                send_json(conn, {
                    "type": "ACK",
                    "echo": msg.get("payload", ""),
                    "server_time": time.time()
                })

            elif mtype == "FILE":
                # Réception d'un fichier (en V1, le contenu est envoyé en clair dans payload)
                filename = msg.get("filename", "received.txt")
                data = msg.get("payload", "")

                print(f"[FILE] Reçu fichier {filename} de {addr}, taille: {len(data)} octets")

                # Reconstruction du fichier côté serveur
                # Ici, on écrit en texte UTF-8 car payload est une chaîne
                with open(f"receive_{filename}", "w", encoding="utf-8") as f:
                    f.write(data)

                # Accusé de réception spécifique au fichier
                send_json(conn, {
                    "type": "ACK_FILE",
                    "filename": filename,
                    "size": len(data),
                    "server_time": time.time()
                })

            elif mtype == "PING":
                # Ping/Pong pour test de connectivité
                send_json(conn, {
                    "type": "PONG",
                    "server_time": time.time()
                })

            else:
                # Type inconnu: on renvoie une erreur
                send_json(conn, {
                    "type": "ERR",
                    "message": "unknown type",
                    "server_time": time.time()
                })

    except Exception as e:
        # On capture et affiche l'erreur pour debug (très utile en réseau)
        print(f"[!] Erreur avec {addr}: {e}")

    finally:
        # On ferme proprement le flux puis la socket
        try:
            sock_file.close()
        except Exception:
            pass

        conn.close()
        print(f"[+] Connexion fermée: {addr}")


def main():
    # Création d'un socket IPv4 TCP:
    # AF_INET => IPv4, SOCK_STREAM => TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

        # SO_REUSEADDR permet de relancer le serveur rapidement après arrêt
        # (sinon le port peut rester occupé temporairement)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # On lie le socket à l'IP et au port
        s.bind((HOST, PORT))

        # Le serveur commence à écouter
        # 5 = taille de la file d'attente des connexions en attente
        s.listen(5)
        print(f"[*] Serveur en écoute sur {HOST}:{PORT}")

        # Boucle infinie: accepte de nouveaux clients
        while True:
            conn, addr = s.accept()
            print(f"[+] Nouvelle connexion de {addr}")

            # Thread par client: permet de gérer plusieurs connexions simultanément
            client_thread = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            )
            client_thread.start()


if __name__ == "__main__":
    main()
