"""
Numéros des points de la main :
    0 = poignet
    4 = bout du pouce      3 = articulation du pouce
    8 = bout de l'index    7, 6 = articulations de l'index
    12 = bout du majeur    11, 10
    16 = bout annulaire    15, 14
    20 = bout auriculaire  19, 18
"""

import time

import mediapipe as mp

POUCE_LEVE = "Pouce leve"
POUCE_BAISSE = "Pouce baisse"
MAIN_OUVERTE = "Main ouverte"
ROND = "Rond"
TROIS = "3"
L = "L"
L_INVERSE = "L inverse"
MAIN_FERMEE = "Main fermee"
AUCUN = "Aucun"

# Tolérance pour doigt horizontal
SEUIL_HORIZONTAL = 0.02


def detecter_geste_main(main):
    y = [point.y for point in main.landmark] 

    # Pouce levé 
    if all(y[4] <= autre_y for autre_y in y):
        return POUCE_LEVE

    # Pouce baissé 
    if all(y[4] >= autre_y for autre_y in y):
        return POUCE_BAISSE

    # Main ouverte 
    if (y[4] < y[3] and y[8] < y[7] and y[12] < y[11]
            and y[16] < y[15] and y[20] < y[19]):
        return MAIN_OUVERTE

    # Rond : index replié, les trois autres doigts levés
    if y[8] > y[6] and y[12] < y[10] and y[16] < y[14] and y[20] < y[18]:
        return ROND

    # 3 : pouce, index et majeur levés, annulaire et auriculaire baissés
    if (y[4] < y[3] and y[8] < y[6] and y[12] < y[10]
            and y[16] > y[14] and y[20] > y[18]):
        return TROIS

    # L : pouce horizontal, index levé, autres doigts baissés
    if (abs(y[4] - y[3]) < SEUIL_HORIZONTAL and y[8] < y[6]
            and y[12] > y[10] and y[16] > y[14] and y[20] > y[18]):
        return L

    # L inversé : pouce baissé, index horizontal, autres doigts baissés
    if (y[4] > y[3] and abs(y[8] - y[6]) < SEUIL_HORIZONTAL
            and y[12] > y[10] and y[16] > y[14] and y[20] > y[18]):
        return L_INVERSE

    return MAIN_FERMEE


def est_doctor_strange(gestes):
    # 3+main ouverte
    return TROIS in gestes and MAIN_OUVERTE in gestes


def bras_croises(pose_landmarks):
    if pose_landmarks is None:
        return False

    points = pose_landmarks.landmark
    poignet_gauche = points[mp.solutions.pose.PoseLandmark.LEFT_WRIST]
    poignet_droit = points[mp.solutions.pose.PoseLandmark.RIGHT_WRIST]

    # On ignore si les poignets sont mal vus 
    if poignet_gauche.visibility < 0.5 or poignet_droit.visibility < 0.5:
        return False

    return poignet_gauche.x < poignet_droit.x


class GesteMaintenu:

    def __init__(self, duree):
        self.duree = duree        # temps de maintien nécessaire
        self.geste = None         # geste en cours d'observation
        self.debut = 0.0          # moment où ce geste a commencé
        self.deja_declenche = False

    def mettre_a_jour(self, geste):
        if geste != self.geste:   # nouveau geste, on relance le chrono
            self.geste = geste
            self.debut = time.monotonic()
            self.deja_declenche = False

    def temps_tenu(self):
        return time.monotonic() - self.debut

    def est_stable(self):
        return self.temps_tenu() >= self.duree

    def declencher_une_fois(self):
        if self.est_stable() and not self.deja_declenche:
            self.deja_declenche = True
            return True
        return False

    def progression(self):
        return min(1.0, self.temps_tenu() / self.duree)
