# Klipper extras module for BMCU-C integration with Happy Hare
#
# Copyright (C) 2025  Jules <jules@bret.aq>
#
# This file may be distributed under the terms of the GNU GPLv3 license.

# --- ATTENTION ---
# Ce module est une PREUVE DE CONCEPT et n'est PAS FONCTIONNEL en l'état.
# Le protocole de communication "bambubus" du BMCU-C est complexe et n'a pas pu
# être entièrement rétro-analysé sans accès au matériel.
#
# Prochaines étapes pour un développeur :
# 1. BAUD RATE : Le firmware utilise 1250000 baud. PySerial sur de nombreux systèmes
#    ne supporte pas cette vitesse. Une recompilation de Klipper ou une solution
#    alternative peut être nécessaire. Le baud rate a été laissé à 115200 par défaut.
# 2. STRUCTURE DES PAQUETS : La fonction `_send_command` est une simplification.
#    Il faut l'adapter pour qu'elle corresponde exactement aux paquets courts et longs
#    du firmware C++, en gérant correctement les adresses, les numéros de paquets, etc.
# 3. LOGIQUE DE PAYLOAD : Le payload envoyé par `cmd_BMCU_SELECT_GATE` est une
#    supposition. Il doit être validé par des tests matériels.
# 4. GESTION DES RÉPONSES : Le code n'implémente pas la lecture et l'interprétation
#    des réponses du BMCU-C, ce qui est essentiel pour un fonctionnement en boucle fermée.
# 5. COMMANDES SIMULÉES : Les commandes HOME et CHECK_GATE sont simulées car elles
#    ne semblent pas avoir de mapping direct. La logique de statut doit être implémentée
#    en écoutant les messages périodiques du BMCU-C.

import serial
import logging

# ... (le reste du code reste identique) ...
# Implémentation du checksum CRC8 DVB-S2, utilisé par le protocole "bambubus"
def crc8_dvb_s2(data):
    crc = 0x66
    poly = 0x39
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
    return crc & 0xff

# Implémentation du checksum CRC16 non standard utilisé par le protocole "bambubus"
def crc16_bambu(data):
    crc = 0x913D
    poly = 0x1021
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
    return crc & 0xFFFF

class BMCU:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')

        serial_port = config.get('serial')
        baud_rate = config.getint('baud', 115200) # ATTENTION: Doit être 1250000 pour le matériel réel

        try:
            self.serial_conn = serial.Serial(serial_port, baud_rate, timeout=1, parity=serial.PARITY_EVEN, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE)
        except serial.SerialException as e:
            raise config.error("Impossible d'ouvrir le port série BMCU: %s" % (e,))

        self.gcode.register_command("BMCU_SELECT_GATE", self.cmd_BMCU_SELECT_GATE, desc=self.cmd_BMCU_SELECT_GATE_help)
        self.gcode.register_command("BMCU_HOME", self.cmd_BMCU_HOME, desc=self.cmd_BMCU_HOME_help)
        self.gcode.register_command("BMCU_CHECK_GATE", self.cmd_BMCU_CHECK_GATE, desc=self.cmd_BMCU_CHECK_GATE_help)

        logging.info("Module BMCU-C (preuve de concept) initialisé sur %s" % serial_port)

    def _send_command(self, cmd_type, payload=b''):
        """(Simplifié) Construit et envoie un paquet court au BMCU-C."""
        header = bytearray([0x3D, 0xC5])
        body = bytearray([cmd_type]) + payload
        length = len(body) + 8
        header_for_crc = header + bytearray([length, 0x00, cmd_type]) # Simplification
        crc8_header = crc8_dvb_s2(header_for_crc)
        packet_pre_crc16 = header + bytearray([length, crc8_header, cmd_type]) + payload
        crc16_body = crc16_bambu(packet_pre_crc16)
        final_packet = packet_pre_crc16 + bytearray([crc16_body & 0xFF, (crc16_body >> 8) & 0xFF])

        logging.debug("Envoi au BMCU (PoC): %s", final_packet.hex())
        # self.serial_conn.write(final_packet) # Désactivé pour la sécurité

    cmd_BMCU_SELECT_GATE_help = "Sélectionne une porte sur le BMCU-C"
    def cmd_BMCU_SELECT_GATE(self, gcmd):
        gate = gcmd.get_int('GATE', minval=0, maxval=3)
        self.gcode.respond_info("BMCU (PoC): Commande de sélection pour la porte %d" % gate)
        payload = bytearray([0x00, 0x03, gate, 0x00]) # Payload supposé
        self._send_command(0x03, payload=payload)

    cmd_BMCU_HOME_help = "Initialise le BMCU-C (SIMULÉ)"
    def cmd_BMCU_HOME(self, gcmd):
        self.gcode.respond_info("BMCU (PoC): Homing (SIMULÉ, non implémenté)")

    cmd_BMCU_CHECK_GATE_help = "Vérifie le filament (SIMULÉ)"
    def cmd_BMCU_CHECK_GATE(self, gcmd):
        gate = gcmd.get_int('GATE', minval=0, maxval=3)
        self.gcode.respond_info("BMCU (PoC): Demande de statut pour la porte %d (SIMULÉ, non implémenté)" % gate)

def load_config(config):
    return BMCU(config)
