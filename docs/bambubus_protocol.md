# Protocole bambubus du BMCU-C (firmware v0020)

Ce document résume la structure des trames échangées entre le contrôleur
**BMCU-C** et l'hôte Klipper sur le bus RS‑485 « bambubus ». Les informations ont
été extraites du firmware de référence v0020 et mises en œuvre dans
`klipper/klippy/extras/bmcu.py`.

## Cadencement et couche physique

- **Vitesse** : 1 250 000 bauds.
- **Trame UART** : 8 bits de données, parité paire, 1 bit de stop.
- **Différentiel** : liaison RS‑485 demi‑duplex via le transceiver TP75176E.

Ces paramètres sont ceux employés par le firmware d'origine et utilisés par le
pilote Klipper lors de l'ouverture du port série.【F:klipper/klippy/extras/bmcu.py†L120-L150】

## En-tête commun

Chaque message débute par le mot de synchronisation `0x3D 0xC5`, suivi d'un
champ de longueur et d'un en-tête logique :

| Champ            | Taille | Description |
| ---------------- | ------ | ----------- |
| `preamble`       | 2 octets | Constante `0x3D 0xC5`. |
| `length`         | 1 ou 2 octets | Taille du message (hors préambule). |
| `sequence`       | 1 octet | Compteur modulo 256, incrémenté à chaque trame émise. |
| `src` / `dst`    | 1 octet chacun | Adresse logique de l'émetteur et du récepteur. |
| `command`        | 1 octet | Identifiant de commande. |
| `header_crc8`    | 1 octet | CRC8 DVB‑S2 appliqué à tous les octets précédents. |
| `payload`        | `N` octets | Données associées à la commande. |
| `crc16`          | 2 octets | CRC16 propriétaire calculé sur l'ensemble de la trame sauf `crc16`. |

Le CRC8 emploie un polynôme `0x39`, une valeur initiale `0x66` et est évalué sur
le préambule, la longueur et les champs `sequence/src/dst/command`. Le CRC16
utilise le polynôme `0x1021` avec une initialisation `0x913D`, le résultat étant
encodé en little‑endian.【F:klipper/klippy/extras/bmcu.py†L38-L79】

## Trames courtes et longues

Le firmware distingue deux types de paquets selon le volume du payload :

- **Trame courte** : le champ `length` tient sur un octet (`bit7=0`) et indique
  `len(payload) + 8`. On peut transmettre jusqu'à 55 octets de charge utile.
- **Trame longue** : le champ `length` s'étale sur deux octets. Le bit 7 du
  premier octet est positionné (`1xxx xxxx`) et les 14 bits restants encodent
  `len(payload) + 9`, pour un maximum de 0x3FFF octets.【F:klipper/klippy/extras/bmcu.py†L64-L113】

Le pilote gère automatiquement la transition vers le format long dès que la
charge utile dépasse le seuil de la trame courte.【F:klipper/klippy/extras/bmcu.py†L86-L105】

## Commandes et réponses

Les identifiants ci-dessous proviennent des tables de dispatch du firmware et
sont exposés dans le pilote Klipper :

| Identifiant | Direction | Description |
| ----------- | --------- | ----------- |
| `0x01` (`CMD_PING`) | Host → BMCU | Keepalive / présence. |
| `0x02` (`CMD_HOME`) | Host → BMCU | Démarrage mécanique du buffer. |
| `0x03` (`CMD_SELECT_GATE`) | Host → BMCU | Sélection d'une porte (payload : octets réservés + index). |
| `0x04` (`CMD_QUERY_STATUS`) | Host ↔ BMCU | Lecture ponctuelle de l'état d'une porte ou du buffer. |
| `0x80` | BMCU → Host | Accusé de réception (`RSP_ACK_MASK` appliqué à la commande d'origine). |
| `0x90` (`RSP_STATUS`) | BMCU → Host | Publication périodique de l'état du buffer. |
| `0x91` (`RSP_ERROR`) | BMCU → Host | Notification d'erreur (payload : code d'erreur). |

La mise en œuvre dans `bmcu.py` traduit ces commandes en G-code et interprète
les réponses pour mettre à jour l'état de Klipper.【F:klipper/klippy/extras/bmcu.py†L27-L33】【F:klipper/klippy/extras/bmcu.py†L184-L278】

## Structure du paquet `RSP_STATUS`

Les observations du firmware montrent que le payload de `RSP_STATUS` suit la
structure suivante :

| Octet | Signification |
| ----- | ------------- |
| `0`   | Bits d'ouverture des portes (`bit0` → porte 0, etc.). |
| `1`   | Présence de filament (`bit0` → porte 0, etc.). |
| `2`   | Code d'erreur courant (0 = aucun). |
| `3`   | Porte active (0–3). |
| `4`   | Flags divers (ex. homing terminé). |

Le pilote convertit ces informations en un dictionnaire exposé via
`get_status`, conserve un historique des 10 derniers codes d'erreur et signale
les changements par des logs de debug.【F:klipper/klippy/extras/bmcu.py†L184-L241】

## Séquencement et temporisation

Chaque trame émise incrémente le compteur de séquence modulo 256. Le pilote
registre également la dernière activité vue sur le bus et envoie un `PING`
initial au démarrage afin de synchroniser la numérotation. Un timer périodique
(`0,5 s`) déclenche des requêtes d'état tant que le BMCU est marqué comme en
ligne.【F:klipper/klippy/extras/bmcu.py†L152-L209】

## Journalisation et surveillance

Tous les échanges sont consignés en niveau DEBUG, avec mise en évidence des
CRC invalides et des codes d'erreur remontés par le BMCU. Cette journalisation
facilite la rétro‑analyse de nouvelles commandes et l'ajout de capteurs
supplémentaires.【F:klipper/klippy/extras/bmcu.py†L95-L104】【F:klipper/klippy/extras/bmcu.py†L210-L241】
