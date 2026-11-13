#Lance les deux nœuds d'un coup : ros2 launch tello_gestes tello.launch.py

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="tello_gestes", executable="tello_driver", output="screen"),
        Node(
            package="tello_gestes",
            executable="controleur",
            output="screen",
            parameters=[{
                "vitesse_gestes": 0.3,        # vitesse en mode gestes (0 à 1)
                "vitesse_max_suivi": 0.4,     # vitesse max en mode suivi (0 à 1)
                "taille_visage_cible": 0.15,  # largeur du visage voulue (fraction de l'image)
            }],
        ),
    ])
