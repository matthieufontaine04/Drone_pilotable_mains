"""
Publie :
    /tello/image_raw : la vidéo du drone
    /tello/batterie : batterie en %
    /tello/en_vol : True si le drone vole

Écoute :
    /tello/cmd_vel : vitesses
                       linear.x  > 0 : avancer
                       linear.y  > 0 : aller à gauche
                       linear.z  > 0 : monter
                       angular.z > 0 : tourner à gauche 
    /tello/commande: "decoller", "atterrir", "urgence"

"""

import time

import rclpy
from rclpy.node import Node
from cv_bridge import CvBridge
from djitellopy import Tello
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32, String

VITESSE_MAX_TELLO = 100     # val entre 100 et 200
DELAI_SECURITE = 0.5        # secondes sans ordre avant de s'arrêter


def limiter(valeur):
    """Convertit une vitesse entre -1 et 1 en entier entre -100 et 100."""
    valeur = max(-1.0, min(1.0, valeur))
    return int(valeur * VITESSE_MAX_TELLO)


class TelloDriver(Node):

    def __init__(self):
        super().__init__("tello_driver")

        #Connexion au drone
        self.tello = Tello()
        self.tello.connect()
        self.get_logger().info(f"Connecté ! Batterie : {self.tello.get_battery()} %")
        self.tello.streamon()
        self.lecteur_video = self.tello.get_frame_read()
        self.bridge = CvBridge()

        #Publications et abonnements
        self.pub_image = self.create_publisher(Image, "/tello/image_raw", 1)
        self.pub_batterie = self.create_publisher(Int32, "/tello/batterie", 1)
        self.pub_en_vol = self.create_publisher(Bool, "/tello/en_vol", 1)
        self.create_subscription(Twist, "/tello/cmd_vel", self.recevoir_vitesse, 1)
        self.create_subscription(String, "/tello/commande", self.recevoir_commande, 10)

        #Dernière vitesse reçue
        self.derniere_vitesse = Twist()
        self.heure_derniere_vitesse = 0.0

        #Boucles périodiques
        self.create_timer(1 / 30, self.publier_image)       # 30 images/s
        self.create_timer(1 / 20, self.envoyer_vitesse)     # 20 ordres/s
        self.create_timer(1.0, self.publier_etat)           # toutes les secondes

    #Réception des ordres

    def recevoir_vitesse(self, msg):
        self.derniere_vitesse = msg
        self.heure_derniere_vitesse = time.monotonic()

    def recevoir_commande(self, msg):
        commande = msg.data
        try:
            if commande == "decoller" and not self.tello.is_flying:
                self.get_logger().info("Décollage")
                self.tello.takeoff()
            elif commande == "atterrir" and self.tello.is_flying:
                self.get_logger().info("Atterrissage")
                self.tello.land()
            elif commande == "urgence":
                self.get_logger().warn("ARRÊT D'URGENCE")
                self.tello.emergency()
        except Exception as erreur:
            self.get_logger().error(f"Échec de '{commande}' : {erreur}")

    #Boucles périodiques

    def publier_image(self):
        image = self.lecteur_video.frame
        if image is None:
            return
        msg = self.bridge.cv2_to_imgmsg(image, encoding="rgb8")
        msg.header.stamp = self.get_clock().now().to_msg()
        self.pub_image.publish(msg)

    def envoyer_vitesse(self):
        if not self.tello.is_flying:
            return
        if time.monotonic() - self.heure_derniere_vitesse > DELAI_SECURITE:
            vitesse = Twist()
        else:
            vitesse = self.derniere_vitesse

        self.tello.send_rc_control(
            limiter(-vitesse.linear.y),    # gauche / droite
            limiter(vitesse.linear.x),     # avant / arrière
            limiter(vitesse.linear.z),     # haut / bas
            limiter(-vitesse.angular.z),   # rotation
        )

    def publier_etat(self):
        self.pub_batterie.publish(Int32(data=self.tello.get_battery()))
        self.pub_en_vol.publish(Bool(data=self.tello.is_flying))

    # Arrêt 

    def arreter(self):
        if self.tello.is_flying:
            self.get_logger().info("Arrêt du nœud : atterrissage.")
            self.tello.land()
        self.tello.streamoff()
        self.tello.end()


def main():
    rclpy.init()
    noeud = TelloDriver()
    try:
        rclpy.spin(noeud)
    except KeyboardInterrupt:
        pass
    finally:
        noeud.arreter()
        noeud.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
