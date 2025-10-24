# Utilisation du portage BMCU-C pour Klipper

Ce guide résume la configuration logicielle nécessaire pour piloter le buffer BMCU-C via Klipper.

## 1. Configuration Klipper

Incluez la carte `bmcu_c` dans votre fichier `printer.cfg` :

```ini
[include config/boards/bmcu_c.cfg]
```

Le fichier fournit quatre sections `[manual_stepper]` prêtes à l'emploi qui exposent chacun des moteurs du buffer ainsi que les capteurs Hall correspondants. Il installe également un objet `[neopixel bmcu_c_status]` pour la LED WS2812B et plusieurs macros G-code (`BMCU_ENABLE_SPOOLS`, `BMCU_DISABLE_SPOOLS`, `BMCU_HOME`, `BMCU_SPOOL_MOVE`) pour orchestrer les séquences de chargement/déchargement.【F:klipper/config/boards/bmcu_c.cfg†L1-L134】

Les macros peuvent être appelées directement dans vos scripts :

```gcode
BMCU_ENABLE_SPOOLS
BMCU_SPOOL_MOVE GATE=1 MOVE=120 VELOCITY=25 ACCEL=300
BMCU_HOME
BMCU_DISABLE_SPOOLS
```

## 2. Test de la communication RS-485

Un script Python (`scripts/bmcu_rs485_test.py`) permet d'envoyer un octet de synchronisation 0x18 et d'échantillonner les réponses du microcontrôleur. C'est un moyen simple de vérifier la couche physique RS-485 avant de lancer Klipper.【F:klipper/scripts/bmcu_rs485_test.py†L1-L86】

```bash
python3 scripts/bmcu_rs485_test.py /dev/ttyUSB0 --baud 250000 --payload 766572
```

Ce qui précède envoie le message `0x18 0x76 0x65 0x72` (le mot « ver ») et affiche les octets renvoyés par la carte. Répétez l'opération après avoir branché le bus pour valider la direction demi-duplex.

## 3. Surveillance des capteurs Hall/IR et du courant ISEN

Les alias exposés dans `bmcu_c.cfg` permettent de mapper les entrées Hall (`spool*_hall`) et les voies analogiques IR (`spool*_ir`) afin d'utiliser `QUERY_ENDSTOPS` ou `QUERY_ADC`. Les broches ISEN des ponts H sont accessibles via les canaux ADC du CH32 (option `CONFIG_WANT_ADC` activée dans `menuconfig`).【F:klipper/src/ch32v20x/Kconfig†L6-L13】【F:klipper/src/ch32v20x/pins_bmcu_c.h†L12-L47】

Exemple pour lire le photodiode du premier spool :

```gcode
QUERY_ADC PIN=bmcu_c:spool1_ir
```

## 4. Séquence type de changement de filament

1. `BMCU_ENABLE_SPOOLS`
2. `MANUAL_STEPPER STEPPER=bmcu_c_spool_1 SET_POSITION=0`
3. `BMCU_SPOOL_MOVE GATE=1 MOVE=200`
4. `QUERY_ENDSTOPS`
5. `BMCU_DISABLE_SPOOLS`

Ces commandes peuvent être encapsulées dans un `gcode_macro` spécifique à votre imprimante pour automatiser les changements de filament.
