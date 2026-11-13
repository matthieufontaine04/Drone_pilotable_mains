# tello_gestes — DJI Tello : suivi de visage + pilotage aux gestes (ROS2)

## Organisation

```
tello_gestes/
├── tello_gestes/
│   ├── gestes.py        # reconnaissance des gestes (ton code, rangé en fonctions)
│   ├── tello_driver.py  # nœud qui parle au drone (vidéo, vitesses, décollage...)
│   └── controleur.py    # nœud "cerveau" : suivi du visage + gestes
├── launch/tello.launch.py
├── package.xml
└── setup.py
```

```
 [Tello] --vidéo--> tello_driver --/tello/image_raw--> controleur
 [Tello] <--ordres-- tello_driver <--/tello/cmd_vel---- controleur
                                  <--/tello/commande--
```

## Installation

```bash
pip install djitellopy mediapipe opencv-python
sudo apt install ros-$ROS_DISTRO-cv-bridge

cd ~/ros2_ws/src
# copier le dossier tello_gestes ici
cd ~/ros2_ws
colcon build --packages-select tello_gestes
source install/setup.bash
```

Garde la même version de `mediapipe` que pour ton script d'origine
(le code utilise `mp.solutions`, comme toi).

## Lancement

1. Allume le Tello et connecte ton PC à son Wi-Fi (`TELLO-XXXXXX`).
2. `ros2 launch tello_gestes tello.launch.py`

## Commandes

| Geste / touche | Mode | Action |
|---|---|---|
| Pouce levé 1 s (au sol) | tous | Décoller |
| Bras croisés 1 s | tous | Atterrir |
| "3" + main ouverte 1 s (Doctor Strange) | tous | Changer de mode SUIVI ↔ GESTES |
| Pouce levé | GESTES | Monter |
| Pouce baissé | GESTES | Descendre |
| 3 | GESTES | Le drone avance vers toi |
| Rond | GESTES | Le drone recule |
| L | GESTES | Le drone part vers ta gauche |
| L inversé | GESTES | Le drone part vers ta droite |
| Main ouverte / poing / rien | GESTES | Vol stationnaire |
| `t` / `l` / `m` | — | Décoller / atterrir / changer de mode |
| `espace` | — | **Arrêt d'urgence** (moteurs coupés, le drone tombe) |
| `q` | — | Atterrir et quitter |

En mode SUIVI, le drone tourne et monte/descend pour garder ton visage
sur la croix blanche, et avance/recule pour garder la bonne distance.
Sans visage visible, il reste sur place.

## Réglages

- Drone trop près / trop loin en suivi → `taille_visage_cible` (plus grand = plus près).
- Drone trop mou / trop nerveux → `vitesse_max_suivi`, ou les gains
  `gain_rotation`, `gain_hauteur`, `gain_distance` dans `controleur.py`.
- Couleurs rouge/bleu inversées à l'écran → ta version de djitellopy donne du BGR :
  remplace `"rgb8"` par `"bgr8"` dans `tello_driver.py`.
- Si L / L inversé envoient le drone du mauvais côté, échange leurs lignes
  dans `MOUVEMENTS` (`controleur.py`).

## Sécurité

- Le driver arrête le drone si aucun ordre n'arrive pendant 0,5 s.
- Ctrl+C sur le launch → le drone atterrit.
- Premiers tests : en intérieur dégagé, batterie > 30 %, avec `vitesse_gestes` bas.
