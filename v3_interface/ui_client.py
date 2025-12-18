#ce fichier consiste en une interface graphique pour un client de chat sécurisé utilisant TLS.
#il fait suite au code du client réseau pour permettre aux utilisateurs de se connecter à un serveur,
#d'envoyer des messages et des fichiers via une interface conviviale.

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading  #threading peut servir si on fait des actions UI asynchrones (ici la réception est gérée côté SecureClient)

from client_network import SecureClient


class ChatUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure TLS Chat")
        self.root.geometry("600x500")

        self.client = None  #pour qu'on veut qu'il existe un état initial de client (au début on n'est pas connecté)

        # ----------------- Frame connexion -----------------
        conn_frame = tk.LabelFrame(root, text="Connexion serveur")  #en-tête de la frame
        conn_frame.pack(fill="x", padx=10, pady=5)  #fill x pour avoir toute la largeur et ensuite les dimensions des marges

        #labels permettant d'afficher le texte (infos de connexion)
        tk.Label(conn_frame, text="IP serveur").grid(row=0, column=0)  #label permettant d'afficher le texte
        tk.Label(conn_frame, text="Port").grid(row=0, column=2)
        tk.Label(conn_frame, text="Username").grid(row=0, column=4)

        #champ de saisie pour l'adresse IP
        self.ip_entry = tk.Entry(conn_frame, width=15)
        self.ip_entry.insert(0, "127.0.0.1")  #valeur par défaut
        self.ip_entry.grid(row=0, column=1)

        #entrée pour le port
        self.port_entry = tk.Entry(conn_frame, width=5)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=0, column=3)

        #entrée pour le nom d'utilisateur
        self.user_entry = tk.Entry(conn_frame, width=10)
        self.user_entry.insert(0, "alice")
        self.user_entry.grid(row=0, column=5)

        #bouton pour se connecter au serveur
        self.connect_btn = tk.Button(conn_frame, text="Connecter", command=self.connect)
        self.connect_btn.grid(row=0, column=6, padx=5)

        # ----------------- Zone chat -----------------
        #scrolledtext = zone de texte avec scrollbar intégrée
        #state="disabled" pour empêcher la modification directe (on écrit dedans uniquement via log())
        self.chat_area = scrolledtext.ScrolledText(root, state="disabled", height=20)  #stated disabled pour empêcher la modification directe
        self.chat_area.pack(fill="both", expand=True, padx=10, pady=5)

        # ----------------- Envoi messages -----------------
        send_frame = tk.Frame(root)  #frame pour regrouper le champ message + boutons d'envoi
        send_frame.pack(fill="x", padx=10, pady=5)

        #champ de saisie du message
        self.msg_entry = tk.Entry(send_frame)
        self.msg_entry.pack(side="left", fill="x", expand=True)

        #bouton pour envoyer un message texte
        self.send_btn = tk.Button(send_frame, text="Envoyer message", command=self.send_message)
        self.send_btn.pack(side="left", padx=5)

        #bouton pour envoyer un fichier (on ouvrira un sélecteur de fichier)
        self.file_btn = tk.Button(send_frame, text="Envoyer fichier", command=self.send_file)
        self.file_btn.pack(side="left")

    # -----------------------------------------------------

    def log(self, text):  #cette méthode permet d'afficher les messages dans la zone de chat
        self.chat_area.configure(state="normal")  #configure pour permettre la modification
        self.chat_area.insert(tk.END, text + "\n")  #insertion du texte à la fin
        self.chat_area.configure(state="disabled")  #state disabled après modification
        self.chat_area.see(tk.END)  #see pour faire défiler automatiquement vers le bas

    def connect(self):  #cette méthode est appelée lorsque l'utilisateur clique sur le bouton de connexion
        if self.client:  #si le client existe déjà, on ne fait rien
            return

        #récupération des infos saisies par l'utilisateur
        ip = self.ip_entry.get()
        port = int(self.port_entry.get())
        username = self.user_entry.get()

        try:
            #SecureClient est importé du module client_network
            #il encapsule toute la logique réseau (TLS, envoi JSON, thread de réception)
            self.client = SecureClient(ip, port, username, self.log)  #secureclient est importé du module client_network
            self.client.connect()  #déclenche la connexion TLS + envoi LOGIN + lancement du thread de réception
            self.log("[+] Connecté au serveur TLS")
        except Exception as e:
            #en cas d'erreur (certificat, réseau, etc.), on affiche une popup
            messagebox.showerror("Erreur", str(e))
            self.client = None

    def send_message(self):  #envoi de message
        if not self.client:  #si le client n'est pas connecté, on ne fait rien
            return

        text = self.msg_entry.get()
        if text.strip() == "":
            return

        #envoi via la couche réseau (SecureClient)
        self.client.send_message(text)
        self.log(f"[MOI] {text}")
        self.msg_entry.delete(0, tk.END)

    def send_file(self):  #meme logique
        if not self.client:
            return

        #ouverture d'un sélecteur de fichier
        path = filedialog.askopenfilename()
        if not path:
            return

        #envoi du fichier via SecureClient (le fichier sera lu et envoyé dans un message JSON FILE)
        self.client.send_file(path)
        self.log(f"[MOI] Fichier envoyé : {path}")


if __name__ == "__main__":
    #création de la fenêtre principale Tkinter
    root = tk.Tk()
    app = ChatUI(root)
    root.mainloop()  #boucle principale de l'interface (gère les événements: clics, saisies, etc.)
