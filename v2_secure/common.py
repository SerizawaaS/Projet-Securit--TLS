# common.py
# Ce fichier contient des fonctions communes utilisées
# aussi bien par le client que par le serveur.

import json


def send_json(sock, data):
    """
    Envoie un dictionnaire Python sous forme JSON,
    suivi d'un caractère de fin de ligne (\n).
    """

    # data est un dictionnaire Python
    # json.dumps() convertit le dictionnaire en une chaîne de caractères JSON
    message = json.dumps(data) + "\n"

    # La chaîne JSON est encodée en UTF-8
    # sendall() garantit que toutes les données sont envoyées via la socket
    sock.sendall(message.encode("utf-8"))


def recv_json(sock_file):
    """
    Reçoit un message JSON depuis un flux de lecture
    associé à une socket TCP.
    """

    # sock_file est un objet de type "file-like" obtenu avec sock.makefile()
    # readline() lit le flux caractère par caractère jusqu'à rencontrer '\n'
    # ce qui correspond à un message complet dans notre protocole
    line = sock_file.readline()

    # Si readline() retourne une chaîne vide,
    # cela signifie que la connexion est fermée
    if not line:
        return None

    # json.loads() convertit la chaîne JSON reçue
    # en dictionnaire Python
    return json.loads(line)

