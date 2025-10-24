# Rapport de validation toolchain CH32V203

## Contexte

Une tentative d'installation et de validation de la chaîne GCC RISC-V bare-metal et des exemples WCH a été réalisée depuis l'environnement CI fourni. Les étapes ont suivi les recommandations du guide [`docs/ch32v203_porting_guide.md`](ch32v203_porting_guide.md).

## 1. Installation de `gcc-riscv-none-elf`

L'installation via `apt-get` a échoué en raison de l'absence d'accès réseau sortant vers les dépôts Ubuntu et LLVM. L'exécution de `sudo apt-get update` retourne des erreurs HTTP 403 depuis le proxy de la plateforme, empêchant l'accès aux paquets requis.

- Journal d'échec : voir la sortie du terminal (bloc `cbe902`).
- Version installée : aucune (toolchain non installée).

## 2. Clonage et compilation de l'EVT WCH

Le dépôt `openwch/ch32v20x_EVTR` n'a pas pu être cloné car les connexions HTTPS sortantes sont bloquées (erreur 403 sur l'établissement du tunnel HTTPS). Sans sources locales, la compilation de l'exemple `GPIO_Toggle` n'a pas été possible.

- Journal d'échec : voir la sortie du terminal (bloc `7bf45b`).
- Version EVT validée : aucune (non téléchargée).
- Build : non effectuée.

## 3. Flash et validation sur carte cible

L'environnement CI ne dispose pas d'accès à un programmateur WCH-LinkE ni au matériel CH32V203 physique. Les étapes de connexion SWD, de flash et de vérification du clignotement de la LED PC13 n'ont donc pas pu être exécutées.

- Matériel requis : WCH-LinkE + carte CH32V203.
- Statut : non exécuté (limitation matérielle de l'environnement CI).

## 4. Versions de référence

| Composant                | Version/Statut                                   |
|--------------------------|--------------------------------------------------|
| Toolchain GCC            | Non installée (échec `apt-get update`)          |
| Binutils                 | Non installés                                    |
| Environnement WCH EVT    | Non téléchargé (blocage HTTPS)                   |
| Pilote WCH-LinkE         | Non applicable (aucun périphérique détectable)   |

## Conclusion

Les trois étapes préliminaires (installation toolchain, compilation d'un exemple, flash matériel) ne peuvent pas être menées à bien dans l'environnement d'intégration continue actuel à cause de restrictions réseau et de l'absence d'accès au matériel. Il est recommandé de réaliser ces actions sur une station de développement disposant :

1. D'un accès direct aux dépôts Ubuntu ou d'un miroir local pour installer la toolchain `gcc-riscv-none-elf`.
2. D'un accès Git/HTTPS vers le dépôt officiel `openwch/ch32v20x_EVTR`.
3. D'un programmateur WCH-LinkE connecté à la carte CH32V203 pour la validation matérielle.

Une fois ces conditions remplies, documenter les versions exactes de la toolchain (`riscv-none-elf-gcc --version`), des binutils (`riscv-none-elf-ld --version`), ainsi que la révision exacte de l'EVT utilisée, et confirmer le clignotement de la LED PC13 après flash.
