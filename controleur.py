"""
Deux modes de vol :
SUIVI: le drone garde centre le visage et à bonne distance.
GESTES: le drone obéit aux gestes de main.

Pouce levé = décoller
Bras croisés = atterrir
Doctor Strange : 3 + main ouverte =  changer de mode

Gestes :
    Pouce levé= monter
    Pouce baissé = descendre
    3  = le drone avance vers toi
    Rond= le drone recule
    L= le drone part vers ta gauche
    L inversé= le drone part vers ta droite
    Main ouverte= stop (vol stationnaire)

Touches de secours clavier:
t = décoller   l = atterrir   m = changer de mode
espace = Kill switch   q = atterrir et quitter
"""

import cv2
import mediapipe as mp
import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32, String

from tello_gestes import gestes as g

MODE_SUIVI = "SUIVI"
MODE_GESTES = "GESTES"

MOUVEMENTS = {
    g.POUCE_LEVE:   (0, 0, 1, 0),     # monter
    g.POUCE_BAISSE: (0, 0, -1, 0),    # descendre
    g.TROIS:        (1, 0, 0, 0),     # avancer
    g.ROND:         (-1, 0, 0, 0),    # reculer
    g.L:            (0, -1, 0, 0),    # droite du drone 
    g.L_INVERSE:    (0, 1, 0, 0),     # gauche du drone 
    g.MAIN_OUVERTE: (0, 0, 0, 0),     # stop
}


class Controleur(Node):

    def __init__(self):
        super().__init__("controleur")

        self.vitesse_gestes = self.declare_parameter("vitesse_gestes", 0.3).value
        self.vitesse_max_suivi = self.declare_parameter("vitesse_max_suivi", 0.4).value
        self.taille_visage_cible = self.declare_parameter("taille_visage_cible", 0.15).value

        # Gains du suivi
        self.gain_rotation = 1.2
        self.gain_hauteur = 1.0
        self.gain_distance = 2.5
        self.zone_morte = 0.05   # évite les erreurs

        self.detecteur_visage = mp.solutions.face_detection.FaceDetection(
            model_selection=1,             
            min_detection_confidence=0.6)
        self.detecteur_mains = mp.solutions.hands.Hands(
            max_num_hands=2, min_detection_confidence=0.6, min_tracking_confidence=0.5)
        self.detecteur_pose = mp.solutions.pose.Pose(
            min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.dessin = mp.solutions.drawing_utils


        self.mode = MODE_SUIVI
        self.en_vol = False
        self.batterie = -1
        self.ordre_tenu = g.GesteMaintenu(duree=1.0)      # décoller, atterrir, mode
        self.mouvement_tenu = g.GesteMaintenu(duree=0.3)  # déplacements

        # ROS 
        self.bridge = CvBridge()
        self.pub_vitesse = self.create_publisher(Twist, "/tello/cmd_vel", 1) #liaison avec le topic cmd_vel du drone
        self.pub_commande = self.create_publisher(String, "/tello/commande", 10) #liaison avec le topic commande du drone
        self.create_subscription(Image, "/tello/image_raw", self.traiter_image, 1) #On abonne les différents topics du drone pour récupérer les informations nécessaires
        self.create_subscription(Bool, "/tello/en_vol", self.recevoir_en_vol, 1)
        self.create_subscription(Int32, "/tello/batterie", self.recevoir_batterie, 1)

        self.get_logger().info("Contrôleur prêt. Lève le pouce pour décoller !")

    # Petits outils

    def recevoir_en_vol(self, msg):
        self.en_vol = msg.data

    def recevoir_batterie(self, msg):
        self.batterie = msg.data

    def envoyer_commande(self, texte):
        self.get_logger().info(f"Commande : {texte}")
        self.pub_commande.publish(String(data=texte))

    def changer_mode(self):
        self.mode = MODE_GESTES if self.mode == MODE_SUIVI else MODE_SUIVI
        self.get_logger().info(f"Mode : {self.mode}")

    @staticmethod
    def borner(valeur, maximum):
        return max(-maximum, min(maximum, valeur))


    def traiter_image(self, msg):
        image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        #Détections
        visage = self.trouver_visage(image_rgb)
        gestes_vus = self.trouver_gestes(image_rgb, image)
        pose = self.detecteur_pose.process(image_rgb).pose_landmarks
        croises = g.bras_croises(pose)

        #du plus prioritaire au moins prioritaire
        if croises:
            evenement = "Bras croises"
        elif g.est_doctor_strange(gestes_vus):
            evenement = "Doctor Strange"
        else:
            evenement = self.geste_principal(gestes_vus)

        self.ordre_tenu.mettre_a_jour(evenement)
        self.mouvement_tenu.mettre_a_jour(evenement)

        # 3. Ordres déclenchés par un geste maintenu
        if self.ordre_tenu.declencher_une_fois():
            if evenement == "Bras croises" and self.en_vol:
                self.envoyer_commande("atterrir")
            elif evenement == g.POUCE_LEVE and not self.en_vol:
                self.envoyer_commande("decoller")
            elif evenement == "Doctor Strange":
                self.changer_mode()

        #Vitesse selon le mode
        if self.mode == MODE_SUIVI:
            vitesse = self.calculer_suivi(visage)
        else:
            vitesse = self.calculer_gestes(evenement)
        self.pub_vitesse.publish(vitesse)

        #Affichage
        self.afficher(image, visage, evenement)
        self.lire_clavier()

    #Détections

    def trouver_visage(self, image_rgb):
        resultat = self.detecteur_visage.process(image_rgb)
        if not resultat.detections:
            return None

        # Si plusieurs visages, on prend le plus large 
        boites = [d.location_data.relative_bounding_box for d in resultat.detections]
        boite = max(boites, key=lambda b: b.width)
        return (boite.xmin + boite.width / 2, boite.ymin + boite.height / 2, boite.width)

    def trouver_gestes(self, image_rgb, image):
        """Renvoie la liste des gestes de toutes les mains visibles (et les dessine)."""
        resultat = self.detecteur_mains.process(image_rgb)
        if not resultat.multi_hand_landmarks:
            return []

        gestes_vus = []
        for main in resultat.multi_hand_landmarks:
            gestes_vus.append(g.detecter_geste_main(main))
            self.dessin.draw_landmarks(image, main, mp.solutions.hands.HAND_CONNECTIONS)
        return gestes_vus

    @staticmethod
    def geste_principal(gestes_vus):
        for geste in gestes_vus:
            if geste != g.MAIN_FERMEE:
                return geste
        return g.MAIN_FERMEE if gestes_vus else g.AUCUN

    #Calcul des vitesses en fonction de la distance et de la position du visage ou des gestes
    def calculer_suivi(self, visage):
        vitesse = Twist()
        if visage is None:
            return vitesse   

        x, y, largeur = visage

        # Erreurs
        erreur_x = x - 0.5                               # > 0 : visage à droite de l'image
        erreur_y = y - 0.4                               # > 0 : visage trop bas
        erreur_distance = self.taille_visage_cible - largeur   # > 0 : visage trop petit 

        # Définition de la zone morte
        if abs(erreur_x) < self.zone_morte:
            erreur_x = 0.0
        if abs(erreur_y) < self.zone_morte:
            erreur_y = 0.0
        if abs(erreur_distance) < 0.02:
            erreur_distance = 0.0

        vmax = self.vitesse_max_suivi
        vitesse.angular.z = self.borner(-self.gain_rotation * erreur_x, vmax) #visage trop à droite
        vitesse.linear.z = self.borner(-self.gain_hauteur * erreur_y, vmax) #visage trop bas
        vitesse.linear.x = self.borner(self.gain_distance * erreur_distance, vmax) #visage trop petit
        return vitesse

    def calculer_gestes(self, evenement):
        vitesse = Twist()
        if evenement in MOUVEMENTS and self.mouvement_tenu.est_stable():
            avant, gauche, haut, rotation = MOUVEMENTS[evenement]
            vitesse.linear.x = avant * self.vitesse_gestes
            vitesse.linear.y = gauche * self.vitesse_gestes
            vitesse.linear.z = haut * self.vitesse_gestes
            vitesse.angular.z = rotation * self.vitesse_gestes
        return vitesse

    #Affichage

    def afficher(self, image, visage, evenement):
        hauteur, largeur, _ = image.shape
        vert, rouge, bleu, blanc = (0, 255, 0), (0, 0, 255), (255, 0, 0), (255, 255, 255)

        # Cadre autour du visage suivi
        if visage is not None:
            x, y, w = visage
            cx, cy, demi = int(x * largeur), int(y * hauteur), int(w * largeur / 2)
            cv2.rectangle(image, (cx - demi, cy - demi), (cx + demi, cy + demi), vert, 2)
            cv2.circle(image, (cx, cy), 5, rouge, -1)

        # Croix au point visé par le suivi
        cible = (largeur // 2, int(0.4 * hauteur))
        cv2.drawMarker(image, cible, blanc, cv2.MARKER_CROSS, 20, 2)

        # Textes d'information
        etat = "EN VOL" if self.en_vol else "AU SOL"
        lignes = [
            (f"Mode : {self.mode}", vert),
            (f"{etat} - Batterie : {self.batterie} %", blanc),
            (f"Geste : {evenement}", bleu),
        ]
        for i, (texte, couleur) in enumerate(lignes):
            cv2.putText(image, texte, (20, 40 + 35 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.8, couleur, 2)

        # Barre de progression 
        if evenement in ("Bras croises", "Doctor Strange", g.POUCE_LEVE):
            progression = self.ordre_tenu.progression()
            cv2.rectangle(image, (20, 150), (20 + int(200 * progression), 165), vert, -1)
            cv2.rectangle(image, (20, 150), (220, 165), blanc, 1)

        cv2.imshow("Tello - suivi et gestes", image)

    def lire_clavier(self):
        touche = cv2.waitKey(1) & 0xFF
        if touche == ord("t"):
            self.envoyer_commande("decoller")
        elif touche == ord("l"):
            self.envoyer_commande("atterrir")
        elif touche == ord("m"):
            self.changer_mode()
        elif touche == ord(" "):
            self.envoyer_commande("urgence")
        elif touche == ord("q"):
            self.envoyer_commande("atterrir")
            raise KeyboardInterrupt   # sort de rclpy.spin


def main():
    rclpy.init()
    noeud = Controleur()
    try:
        rclpy.spin(noeud)
    except KeyboardInterrupt:
        pass
    finally:
        noeud.pub_vitesse.publish(Twist())   # dernier ordre 
        cv2.destroyAllWindows()
        noeud.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
