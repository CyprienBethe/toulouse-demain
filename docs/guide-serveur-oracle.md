# Guide : créer le serveur Oracle Cloud de Toulouse Demain

- **Pour** : Cyprien, débutant ; aucune connaissance de Linux n'est nécessaire.
- **Durée** : 1 h 15 à 1 h 45 si tout va bien. L'attente d'Oracle (création du compte, manque de machines) peut s'y ajouter.
- **Date** : 14 octobre 2026. Écrans et conditions d'Oracle relus le même jour sur les sources citées ([G1], [G2]…, liste en fin de document). Les points marqués **(non vérifié)** n'ont pas pu être relus : ils viennent d'une source secondaire, ou les écrans ne sont visibles qu'avec un compte.
- **À la fin** : l'API répond en HTTPS sur `https://<ton-sous-domaine>.duckdns.org`, le graphe se met à jour seul chaque lundi, et le site est publié par GitHub Pages.

> **Deux secrets dans cette soirée. Ils ne se collent jamais dans une conversation (y compris avec Claude), dans GitHub ou dans un e-mail :**
> 1. la **clé SSH privée** (fichier `id_ed25519`, sans `.pub`) : elle reste sur ton ordinateur ;
> 2. le **jeton DuckDNS** : tu le colles une seule fois, dans le terminal du serveur, quand le script te le demande. Ensuite, il ne quitte plus le serveur.
>
> Le **sous-domaine** DuckDNS et l'**adresse IP** du serveur, eux, ne sont pas secrets : tu peux les donner à l'équipe.

## Ce soir en bref

| Étape | Quoi | Durée |
| --- | --- | --- |
| 0 | Préparer : carte, téléphone, appli d'authentification | 5 min |
| 1 | Créer le compte Oracle Cloud | 20 à 30 min |
| 2 | Créer ta clé SSH sur ton ordinateur | 5 min |
| 3 | Créer la machine (instance) | 10 min, plus l'attente éventuelle |
| 4 | Ouvrir les ports 80 et 443 | 10 min |
| 5 | Créer le sous-domaine DuckDNS | 5 min |
| 6 | Se connecter au serveur et lancer **une** commande | 20 à 30 min, dont 15 à 20 sans rien faire |
| 7 | Vérifier que l'API répond | 5 min |
| 8 | Brancher le site : `site/config.js` et GitHub Pages | 5 à 10 min |

---

## Étape 0 — Préparer (5 min)

- **Une carte bancaire acceptée par Oracle** [G1][G2] : une carte de crédit, ou une carte de débit Visa, Mastercard, American Express ou Discover qui **ne demande pas de code PIN** au paiement en ligne. **Refusées** : cartes de débit à code PIN, cartes virtuelles, à usage unique et prépayées. Oracle ne débite rien : il pose une petite **autorisation temporaire**, levée par la banque en 3 à 5 jours [G2].
- **Ton téléphone portable** : son numéro est demandé à l'inscription, et Oracle peut envoyer un code par SMS [G11] **(non vérifié** sur une page d'Oracle : la page officielle ne parle que de saisir le numéro [G1]**)**.
- **Une appli d'authentification** sur ton smartphone : à la première connexion à la console, Oracle impose une double authentification avec son appli **Oracle Mobile Authenticator** (ou une clé de sécurité FIDO) [G10]. Installe l'appli depuis l'App Store ou le Play Store avant de commencer.
- **Un nom de sous-domaine** pour l'API, par exemple `toulouse-demain` (il donnera `toulouse-demain.duckdns.org`) : lettres minuscules, chiffres et tirets. Prévois un deuxième choix si le premier est pris.

---

## Étape 1 — Créer le compte Oracle Cloud Free Tier (20 à 30 min)

1. Ouvre **https://signup.oraclecloud.com** [G1] (c'est aussi là que mène le bouton « Start for free » de la page oracle.com/cloud/free).
2. **Informations du compte** [G1] :
   - **Country** : France ; ton nom ; ton e-mail (un seul compte Oracle par adresse e-mail).
   - Coche **I am human** et réponds au test.
   - Clique **Verify my email**. Tu reçois un e-mail « Confirm your Oracle cloud account » : clique **Click Here** dans les **30 minutes** (le lien expire ensuite). Tu reviens sur la page d'inscription.
3. **Mot de passe** : au moins 8 caractères, avec 1 minuscule, 1 majuscule, 1 chiffre et 1 caractère spécial ; au plus 40 caractères ; sans espace, sans ton nom ni ton e-mail, sans les caractères `` ` ~ < > \ `` [G1]. Note-le dans ton gestionnaire de mots de passe.
4. **Cloud Account Name** : le nom de ton compte, par exemple `cyprientoulouse`. **Note-le** : on te le demande à chaque connexion. Il ne pourra plus être changé [G11].
5. **Home Region** (région d'origine) : **choix définitif**.

   > « Your home region is the geographic location where your account and identity resources will be created. You can't change this after signing up. » [G1]
   >
   > « You must create the Always Free compute instances in your home region. » [G3]

   Autrement dit : la machine gratuite ne peut exister que dans cette région, pour toute la vie du compte. Pour en changer, il faudrait un nouveau compte (avec une autre adresse e-mail). Les régions européennes sont [G4] :

   | Région | Identifiant | Domaines de disponibilité |
   | --- | --- | --- |
   | France Central (Paris) | `eu-paris-1` | 1 |
   | France South (Marseille) | `eu-marseille-1` | 1 |
   | **Germany Central (Frankfurt)** | `eu-frankfurt-1` | **3** |
   | UK South (London) | `uk-london-1` | **3** |
   | Amsterdam, Milan, Turin, Madrid, Stockholm, Zurich, Newport | … | 1 chacune |

   **Recommandation : Germany Central (Frankfurt).** Quand Oracle manque de machines gratuites, sa consigne est de réessayer « dans un autre domaine de disponibilité » [G2][G3] : Frankfurt en a 3, Paris et Marseille un seul. Pour notre usage, la distance ne compte pas : quelques millisecondes de plus, invisibles à côté du calcul d'un itinéraire. **Non vérifiable** : Oracle ne publie pas la capacité libre de chaque région ; une région très demandée peut être pleine plus souvent. Si Frankfurt n'est pas proposée, prends une région voisine, comme l'indique Oracle [G2].
6. Lis les conditions d'utilisation, puis **Continue** [G1].
7. **Adresse et téléphone**, puis **Continue** [G1]. Si Oracle envoie un code par SMS, saisis-le **(non vérifié)** [G11].
8. **Vérification de paiement** : **Add payment verification method** → **Credit Card**, saisis la carte, puis **Finish** [G1]. Une petite somme peut apparaître sur ton compte bancaire : c'est l'autorisation temporaire, pas un débit [G1][G2].
9. Accepte les conditions et clique **Start my free trial** [G1]. L'offre gratuite comprend un essai de 30 jours avec un crédit : **on ne s'en sert pas**. Seules les ressources « Always Free » nous intéressent ; elles restent gratuites après les 30 jours [G2].
10. Oracle prépare le compte (« provisioning ») : quelques minutes, parfois plus. Tu arrives ensuite sur la **console** d'Oracle Cloud (le site d'administration de ton compte), et tu reçois un e-mail de bienvenue [G1][G2].
11. **Première connexion** : un écran demande d'activer la double authentification. Clique **Enable Secure Verification**, puis scanne le QR code avec Oracle Mobile Authenticator [G10]. Garde les codes de secours (« bypass codes ») s'ils sont proposés.

**Si ça coince**
- *Carte refusée* (« error processing transaction » ou similaire) : essaie une vraie carte de crédit, ou la carte de débit d'une autre banque, sans code PIN en ligne. Les cartes virtuelles et prépayées (comme les cartes virtuelles des banques en ligne) sont refusées [G2]. Sinon, le lien **Chat** du site d'Oracle mène au support [G2].
- *Lien de confirmation expiré* : recommence l'étape 2 (le lien dure 30 minutes) [G1].
- *La console dit que certaines ressources ne sont pas prêtes* : attends quelques minutes ; l'inscription de tous les services prend un peu de temps [G2].
- *Région souhaitée absente de la liste* : prends une région voisine [G2].

**Facultatif, 2 minutes** : une alerte budgétaire. Dans le menu, **Billing & Cost Management → Budgets**, crée un budget de 1 € : tu seras prévenu si quelque chose devenait payant [G11] **(non vérifié** sur une page d'Oracle**)**.

---

## Étape 2 — Créer ta clé SSH sur ton ordinateur (5 min)

La clé SSH remplace le mot de passe pour te connecter au serveur. Elle a deux moitiés : la **clé privée** reste sur ton ordinateur (secret) ; la **clé publique** (fichier `.pub`) est donnée à Oracle.

**macOS ou Linux** : ouvre l'application **Terminal** et tape [G13] :

```bash
ssh-keygen -t ed25519 -C "serveur-toulouse-demain"
```

**Windows 10 ou 11** : ouvre **PowerShell** (menu Démarrer, tape « PowerShell ») et tape la même commande :

```powershell
ssh-keygen -t ed25519 -C "serveur-toulouse-demain"
```

Ce que tu vois, et quoi répondre [G13][G14] :
- `Enter file in which to save the key (…/.ssh/id_ed25519):` → **Entrée** (emplacement par défaut).
  - S'il répond `… already exists. Overwrite (y/n)?`, tu as déjà une clé : réponds **n**, puis passe directement à l'affichage de la clé publique ci-dessous.
- `Enter passphrase (empty for no passphrase):` → choisis une phrase de passe (conseillé : elle protège la clé si ton ordinateur est volé), puis retape-la. Rien ne s'affiche pendant la frappe : c'est normal.

Affiche ensuite la **clé publique** (une seule ligne qui commence par `ssh-ed25519`) :

- macOS ou Linux : `cat ~/.ssh/id_ed25519.pub`
- Windows : `Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub`

Les fichiers sont dans `~/.ssh/` (macOS : `/Users/<toi>/.ssh/`, Linux : `/home/<toi>/.ssh/`) ou `C:\Users\<toi>\.ssh\` sur Windows [G13][G14].

**Si ça coince**
- *Windows : « ssh-keygen n'est pas reconnu »* : le client OpenSSH n'est pas installé. Menu Démarrer → tape « Fonctionnalités facultatives » → **Ajouter une fonctionnalité** → **Client OpenSSH** → **Installer** [G15], puis rouvre PowerShell.
- *Ne jamais envoyer* le fichier `id_ed25519` (sans `.pub`) : seul le `.pub` va chez Oracle.

---

## Étape 3 — Créer la machine (instance) (10 min)

Dans la console Oracle : menu (☰) → **Compute** → **Instances** → **Create instance** [G5]. La page est un assistant en plusieurs parties : *Basic information*, *Security*, *Networking*, *Storage*, *Review*. Oracle prévient que l'ordre affiché peut varier [G5].

1. **Name** : `toulouse-demain`. **Compartment** : laisse la valeur proposée (ton compte).
2. **Placement → Availability domain** : laisse le premier (AD-1). C'est ici que tu changeras en cas de manque de capacité.
3. **Shape** (modèle de machine) : **Change shape** → **Virtual machine** → série **Ampere** → coche **VM.Standard.A1.Flex** [G5]. Règle **Number of OCPUs = 2** et **Amount of memory (GB) = 12**, puis **Select shape**. C'est exactement le maximum gratuit : 2 OCPU et 12 Go au total [G3]. La forme est marquée **Always Free-eligible** [G11] ; la console propose parfois 1 OCPU et 6 Go par défaut [G11] : corrige.
4. **Image** : **Change image** → **Ubuntu** → **Canonical Ubuntu 24.04** → **Select image** [G5]. Prends l'image normale, pas « Minimal ». Pour une machine Ampere, il faut sa version ARM : le nom complet de l'image, visible dans le récapitulatif, contient `aarch64` (par exemple `Canonical-Ubuntu-24.04-aarch64-…`) **(non vérifié** : la console choisit normalement seule la version compatible avec la forme**)**.
5. **Security** : ne change rien [G5].
6. **Networking** [G5] :
   - premier serveur : choisis **Create new virtual cloud network** (le réseau privé de ton compte) et un **sous-réseau public** (« public subnet »), en gardant les noms proposés. Si tu as déjà un réseau : **Select existing virtual cloud network** et son sous-réseau public ;
   - vérifie que **Automatically assign public IPv4 address** est **coché** : sans adresse publique, le serveur est injoignable.
7. **Add SSH keys** : choisis **Paste public keys** et colle la ligne `ssh-ed25519 …` de l'étape 2 (ou **Upload public key files (.pub)** et choisis le fichier `id_ed25519.pub`) [G5]. **Ne prends pas** « Generate a key pair for me » : tu as déjà ta clé.
8. **Storage** : ne change rien. Le disque de démarrage par défaut fait environ 50 Go, dans les 200 Go gratuits [G3].
9. **Review** → **Create** [G5].

**Ce que tu dois voir** : l'état passe de **Provisioning** à **Running** en une à trois minutes. Sur la page de l'instance, note l'**adresse IP publique** (« Public IP address », quatre nombres comme `130.61.x.x`) [G11].

**Si ça coince : « Out of host capacity »** (ou « Out of capacity for shape VM.Standard.A1.Flex… »). Oracle n'a temporairement plus de machines gratuites dans la région [G2][G3]. Dans l'ordre :
1. **Autre domaine de disponibilité** : à l'étape 3.2, choisis AD-2, puis AD-3 (Frankfurt et London en ont trois) [G2][G3][G4].
2. **Réessayer plus tard** : dans une heure, tôt le matin ou le lendemain. D'après Oracle, il peut falloir plusieurs jours pour que de la capacité se libère [G2]. Rien n'est perdu : ton compte et ta clé restent valables.
3. **Plus petit** : 1 OCPU et 6 Go. Le serveur mesuré en CI n'utilise que 1,2 Go ; le script d'installation adapte seul la mémoire de Java à la machine. *Hypothèse* : une petite forme trouve plus facilement de la place.
4. **Passer le compte en « Pay as You Go »** : Oracle le propose ; les ressources Always Free restent gratuites, seul le dépassement serait facturé [G3]. Cela ouvre un **risque de facturation** et contredit la règle « zéro euro » si on se trompe de forme : **c'est ta décision**, l'équipe ne le recommande pas par défaut (ADR 0001, section 3).

---

## Étape 4 — Ouvrir les ports 80 et 443 (10 min)

Deux barrières bloquent le web : la **liste de sécurité** du réseau Oracle (dans la console) et le **pare-feu de la machine**. Les deux doivent laisser passer les ports **80** (HTTP, utilisé pour obtenir le certificat) et **443** (HTTPS) [G7][G8].

### 4.1 Dans la console : la liste de sécurité du réseau (VCN)

Menu (☰) → **Networking** → **Virtual cloud networks** → clique ton réseau (celui créé à l'étape 3) [G6][G7]. Ensuite, selon l'écran que tu as [G6] :
- onglet **Security** → section **Security Lists** → **Default Security List for …** → onglet **Security rules** ;
- ou bien, dans le menu de gauche **Resources** : **Security Lists** → **Default Security List for …** → **Ingress Rules**.

Clique **Add Ingress Rules** [G6][G7] et remplis [G7] :

| Champ | Valeur |
| --- | --- |
| Stateless | **décoché** (valeur par défaut) |
| Source Type | CIDR |
| Source CIDR | `0.0.0.0/0` |
| IP Protocol | TCP |
| Source Port Range | vide |
| Destination Port Range | `80` |
| Description | `HTTP (certificat Let's Encrypt)` |

Ajoute une deuxième règle identique avec **Destination Port Range** `443` et la description `HTTPS (API)`. Le même formulaire propose un bouton pour ajouter une autre règle (libellé du type « + Another Ingress Rule », **non vérifié**) ; sinon, valide puis recommence. Valide avec **Add Ingress Rules**.

**Ce que tu dois voir** : la liste des règles d'entrée contient la règle d'origine pour le port 22 (SSH) et tes deux nouvelles règles, 80 et 443, avec la source `0.0.0.0/0`.

Remarque : le tutoriel d'Oracle coche « Stateless » [G7]. Nous le laissons décoché : une règle « stateful » laisse passer les réponses toute seule, et la règle SSH d'origine fonctionne de la même façon.

### 4.2 Sur la machine : le pare-feu d'Ubuntu (le script s'en charge)

Ce que fait l'image Ubuntu d'Oracle :
- « Instances created using platform images have a default set of firewall rules that allow only SSH access. » [G8] ;
- ces règles sont des règles `iptables`, enregistrées dans `/etc/iptables/rules.v4`, et la liste se termine par une règle qui **rejette** tout le reste ; une règle ajoutée après ce rejet n'a aucun effet [G9][G12] ;
- Oracle déconseille d'utiliser **UFW** sur ses images Ubuntu : il peut empêcher la machine de redémarrer [G8].

**Tu n'as rien à taper** : le script de l'étape 6 ajoute les ports 80 et 443 juste avant la règle de rejet, tout de suite et dans `/etc/iptables/rules.v4` (pour qu'ils restent ouverts après un redémarrage). Il garde une copie du fichier d'origine (`rules.v4.before-toulouse-demain`). **Non vérifié** sur une vraie machine : le contenu exact de `rules.v4` dans l'image Ubuntu 24.04 aarch64 du jour. Les sources décrivent les images Ubuntu d'Oracle en général : [G8] officielle, [G9] de 2022, [G12] de juillet 2026.

Pour mémoire, la méthode manuelle du tutoriel d'Oracle (inutile avec le script) [G7] :

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save
```

Le script n'utilise pas `netfilter-persistent save` : une fois Docker installé, cette commande enregistrerait aussi les règles internes de Docker.

---

## Étape 5 — Créer le sous-domaine DuckDNS (5 min)

1. Va sur **https://www.duckdns.org** et connecte-toi avec ton compte **GitHub** (liens de connexion en haut de la page : Google, GitHub, Twitter… [G16]).
2. Une fois connecté, la page affiche ton **token** (jeton) et une zone **domains** **(libellés non vérifiés** : cette page n'est visible qu'une fois connecté**)**. Dans le champ du sous-domaine, tape le nom choisi à l'étape 0 (par exemple `toulouse-demain`) et clique **add domain**.
3. Ton domaine apparaît avec une adresse IP (souvent celle de ta box, que DuckDNS a détectée). Remplace-la par l'**adresse IP publique du serveur** (étape 3), puis clique **update ip**. Si tu oublies, ce n'est pas grave : le script de l'étape 6 la met à jour lui-même, car DuckDNS enregistre l'adresse de la machine qui l'appelle [G16].
4. **Le jeton** : laisse cet onglet ouvert. Tu le copieras à l'étape 6, au moment où le script le demande, **et nulle part ailleurs**. Si tu penses l'avoir divulgué, le menu de la page de compte permet de le recréer (« recreate token ») [G16] ; relance alors le script de l'étape 6 et réponds « n » à la question « Garder… ».

---

## Étape 6 — Se connecter au serveur et lancer l'installation (20 à 30 min)

### 6.1 Première connexion SSH

Sur ton ordinateur (Terminal sur macOS ou Linux, PowerShell sur Windows), remplace `<IP>` par l'adresse IP publique du serveur :

```bash
ssh ubuntu@<IP>
```

Le compte s'appelle `ubuntu` sur les images Ubuntu d'Oracle [G11].

**Ce que tu dois voir** :
- la première fois : `The authenticity of host '<IP>' can't be established. ED25519 key fingerprint is SHA256:…` puis `Are you sure you want to continue connecting (yes/no/[fingerprint])?` → tape **yes** puis Entrée. C'est normal : ton ordinateur découvre ce serveur ;
- la phrase de passe de ta clé, si tu en as mis une ;
- puis un message de bienvenue d'Ubuntu et une invite qui ressemble à `ubuntu@toulouse-demain:~$`. Tu es sur le serveur.

**Si ça coince**
- *`Permission denied (publickey)`* : la clé collée à l'étape 3.7 n'est pas celle de cet ordinateur, ou le nom d'utilisateur n'est pas `ubuntu`. Vérifie la ligne `.pub` ; au besoin, recrée l'instance avec la bonne clé.
- *`Connection timed out`* : l'instance n'est pas encore « Running », l'IP est fausse, ou l'adresse publique n'a pas été attribuée (étape 3.6).

### 6.2 Une seule commande

Copie cette ligne entière dans la session SSH, puis Entrée :

```bash
curl -fsSLO https://raw.githubusercontent.com/CyprienBethe/toulouse-demain/main/deploy/bootstrap.sh && sudo bash bootstrap.sh
```

Elle télécharge le script d'installation depuis le dépôt, puis le lance avec les droits d'administrateur (`sudo`).

**Ce que tu dois voir, dans l'ordre** :
1. `==> Installation du serveur Toulouse Demain`, puis `1/9 Dépôt toulouse-demain` : le dépôt est copié dans `~/toulouse-demain`.
2. `2/9 Sous-domaine DuckDNS…` et **deux questions** :
   - `Sous-domaine (ce qui précède .duckdns.org) :` → tape `toulouse-demain` (ou ton nom), Entrée ;
   - `Jeton DuckDNS (rien ne s'affiche quand tu colles, c'est normal) :` → colle le jeton copié sur duckdns.org, Entrée. **Rien ne s'affiche** : c'est voulu ;
   - le script répond `jeton reçu (36 caractères, non affiché)` puis `DuckDNS answer for …: OK <IP> UPDATED` (ou `NOCHANGE` si l'adresse était déjà la bonne) ; `<IP>` doit être l'adresse publique du serveur. Si DuckDNS refuse (`KO`), il repose les questions (trois essais).
3. Ensuite, **15 à 20 minutes sans rien faire** : `3/9` mises à jour de sécurité automatiques, `4/9` SSH par clé uniquement (ta session reste ouverte), `5/9` pare-feu, `6/9` Docker, `7/9` téléchargement du graphe puis démarrage d'OpenTripPlanner et de Caddy (la construction de l'image Caddy est la partie la plus longue), `8/9` tâches automatiques.
4. `9/9 Vérifications` : graphe chargé, certificat HTTPS obtenu, API joignable, pages internes d'OTP bien cachées (404).
5. `==> Terminé !` avec **la ligne à mettre dans `site/config.js`** (étape 8) et une commande de vérification.

Ce que le script fait, en détail : voir l'en-tête de `deploy/bootstrap.sh`. On peut le relancer sans risque : il saute ce qui est déjà fait. Son journal complet est dans `/var/log/toulouse-demain-bootstrap.log` (lisible avec `sudo less /var/log/toulouse-demain-bootstrap.log`) ; il ne contient pas le jeton.

**Si ça coince**
- *Le script s'arrête sur `ERREUR : …`* : le message dit quoi faire. Une fois le problème réglé, relance **la même commande** (`sudo bash bootstrap.sh` suffit : le fichier est déjà là).
- *`Le certificat HTTPS n'est pas encore obtenu`* : presque toujours l'étape 4.1 (ports 80 et 443 absents de la liste de sécurité) ou un sous-domaine qui ne pointe pas encore vers le serveur. Corrige, puis tape `cd ~/toulouse-demain/deploy && sudo docker compose restart caddy` et attends une minute ; ou relance le script.
- *`Could not get lock /var/lib/dpkg/lock`* : une mise à jour automatique tourne juste après le démarrage. Le script attend jusqu'à 10 minutes ; au-delà, relance-le.
- *Téléchargement du graphe en échec* : une construction tourne peut-être sur GitHub au même moment. Réessaie dans 10 minutes.

---

## Étape 7 — Vérifier que l'API répond (5 min)

Depuis **ton ordinateur** (pas depuis le serveur), remplace `SOUS-DOMAINE` par le tien.

**macOS ou Linux** (Terminal) :

```bash
curl -s https://SOUS-DOMAINE.duckdns.org/otp/gtfs/v1 -H 'Content-Type: application/json' -d '{"query":"{ feeds { feedId } }"}'
```

**Windows** (PowerShell : la commande `curl` de Windows PowerShell n'est pas le vrai curl, on utilise l'équivalent natif) :

```powershell
Invoke-RestMethod -Method Post -Uri https://SOUS-DOMAINE.duckdns.org/otp/gtfs/v1 -ContentType 'application/json' -Body '{"query":"{ feeds { feedId } }"}' | ConvertTo-Json -Depth 5
```

**Ce que tu dois voir** : les trois flux du graphe, `tisseo`, `sncf` et `futur`, dans n'importe quel ordre. Sur macOS ou Linux, sur une seule ligne :

```json
{"data":{"feeds":[{"feedId":"tisseo"},{"feedId":"sncf"},{"feedId":"futur"}]}}
```

Deux contrôles de plus, dans ton navigateur :
- `https://SOUS-DOMAINE.duckdns.org/meta/scenario-filters.json` affiche un fichier JSON (les filtres des deux scénarios) ;
- `https://SOUS-DOMAINE.duckdns.org/` affiche `Not found` : **c'est normal et voulu**. Seules l'API et ces fichiers sont publics.

**Si ça coince**
- *Erreur de certificat ou délai dépassé* : reprends « Si ça coince » de l'étape 6.
- *`Not found` sur l'API* : vérifie l'adresse : `/otp/gtfs/v1`, sans barre finale.
- *`502 Bad Gateway`* : OpenTripPlanner redémarre (après une mise à jour du graphe, environ 10 s) ; réessaie une minute plus tard.

---

## Étape 8 — Brancher le site (5 à 10 min)

### 8.1 La ligne de `site/config.js`

Le script l'affiche à la fin de l'étape 6, avec ton sous-domaine. Elle a cette forme :

```js
export const API_BASE_URL = "https://SOUS-DOMAINE.duckdns.org";
```

Sans barre finale : le site y ajoute lui-même `/otp/gtfs/v1` et `/meta/…`. Tu peux simplement donner le **sous-domaine** au chef de projet (ce n'est pas un secret), qui fera la modification. Pour la faire toi-même : sur GitHub, ouvre `site/config.js`, clique le crayon (**Edit**), remplace la ligne qui définit `API_BASE_URL`, puis **Commit changes**. Le fichier `site/` est écrit par le développeur front-end : si la ligne n'a pas exactement ce nom, demande-lui.

### 8.2 Activer GitHub Pages

Sur la page du dépôt GitHub : **Settings** → dans la barre de gauche, section « Code, planning, and automation » : **Pages** → **Build and deployment** → **Source** : **GitHub Actions** [G19]. C'est tout : le site est publié par le workflow du dépôt à chaque modification de `main`. GitHub Pages est gratuit pour un dépôt public [G19].

**Ce que tu dois voir** : après la prochaine exécution du workflow du site (onglet **Actions**), le site s'ouvre sur `https://cyprienbethe.github.io/toulouse-demain/`. C'est cette origine, `https://cyprienbethe.github.io`, que le serveur autorise (CORS). Si aucun déploiement n'apparaît, le workflow du site n'est sans doute pas encore fusionné dans `main` : demande au chef de projet.

---

## Après ce soir

**Ce qui tourne tout seul**
- Mises à jour de sécurité d'Ubuntu, chaque jour, sans redémarrage automatique [G18]. Quand Ubuntu affiche `*** System restart required ***` à la connexion, tape `sudo reboot` : tout redémarre seul en deux minutes environ.
- Graphe : chaque lundi vers 06 h 30 UTC, après sa construction par GitHub Actions (03 h 17 UTC). Si la release n'a pas changé, rien n'est redémarré.
- DuckDNS : toutes les 30 minutes, le sous-domaine est recalé sur l'adresse du serveur.
- Certificat HTTPS : renouvelé par Caddy.

**Ce qu'il faut faire à la main**
- **Se connecter à la console Oracle au moins une fois par mois** : un compte inactif 30 jours peut être suspendu, voire supprimé avec la machine [G2].
- Dans une semaine : console Oracle → ton instance → **Metrics** ; la mémoire doit rester vers 50 %. Oracle peut récupérer une instance gratuite si, sur 7 jours, processeur, réseau **et** mémoire restent tous sous 20 % [G3] ; le réglage de Java occupe volontairement environ la moitié de la mémoire (*hypothèse* à confirmer, ADR 0001, section 3).

**Commandes utiles** (dans une session SSH)

| Pour | Commande |
| --- | --- |
| Voir l'état des services | `cd ~/toulouse-demain/deploy && docker compose ps` |
| Lire les messages d'OTP ou de Caddy | `docker compose logs --tail 50 otp` (ou `caddy`) |
| Appliquer une nouvelle version du dépôt | `sudo bash ~/toulouse-demain/deploy/bootstrap.sh` (il fait le `git pull`) |
| Forcer le téléchargement du graphe | `~/toulouse-demain/deploy/update-graph.sh --force` |
| Voir les tâches automatiques | `systemctl list-timers 'toulouse-demain-*'` |
| Interface de débogage d'OTP, en privé | sur ton ordinateur : `ssh -L 8080:127.0.0.1:8080 ubuntu@<IP>`, puis http://localhost:8080 |

`docker` sans `sudo` ne marche qu'après une nouvelle connexion SSH (le script t'a ajouté au groupe `docker`).

---

## Ce qui est exposé sur Internet

| Adresse | Public ? |
| --- | --- |
| `POST /otp/gtfs/v1` (API GraphQL d'OTP 2.10.0 [G20]) | oui, limité à 30 requêtes par minute et par adresse IP, 600 par minute au total, 32 Ko par requête (*hypothèses*, réglables dans `deploy/.env`) |
| `GET /meta/scenario-filters.json`, `GET /meta/scenario-2028.json` | oui (fichiers de la release installée) |
| Tout le reste : interface de débogage, GraphiQL, API Transmodel, actuator [G21], métriques, ancienne adresse GraphQL | **non** : réponse 404 |
| Port 8080 d'OTP | seulement depuis le serveur lui-même (tunnel SSH) |

Le navigateur n'accepte les réponses que pour le site `https://cyprienbethe.github.io` (CORS) ; une requête envoyée par la page d'un autre site est refusée (403). Aucune adresse IP n'est enregistrée (pas de journal d'accès).

## Ce qui n'a pas été testé

- **Rien de ce guide n'a été déroulé sur un vrai compte Oracle** : l'équipe n'a pas accès à Oracle depuis son environnement. Les écrans viennent des pages citées, et les libellés peuvent avoir changé.
- `deploy/bootstrap.sh` **n'a pas tourné sur une vraie machine** Ubuntu 24.04 ARM64. Il a été vérifié par `bash -n` et `shellcheck` 0.11.0, par des tests de ses fonctions (fichier `.env`, règles du pare-feu, saisies) et par un essai complet où les commandes système (apt, Docker, systemd, iptables, réseau) étaient remplacées par des doublures. Cet essai a vérifié que le jeton n'apparaît ni à l'écran, ni dans le journal, ni dans les arguments des commandes.
- Le `Caddyfile` a été testé avec le binaire officiel Caddy 2.11.7, sans le module de limitation de débit (absent du binaire officiel) et en HTTP local : routes publiques, 404 partout ailleurs, CORS, réponse aux requêtes préliminaires, 403 pour un autre site, 413 au-delà de 32 Ko, en-têtes sur les erreurs. La version complète, avec le module, est validée par le workflow `checks.yml`. Non testés : l'obtention réelle du certificat et la limitation de débit en fonctionnement.
- Le contenu exact du pare-feu de l'image Ubuntu 24.04 aarch64 d'Oracle (étape 4.2).

## Sources

Consultées le 14/10/2026. Date de dernière modification de la page indiquée quand elle est connue.

- [G1] Oracle, *Sign Up for the Free Oracle Cloud Promotion* (24/07/2025) : https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm
- [G2] Oracle, *Oracle Cloud Free Tier FAQ* : https://www.oracle.com/cloud/free/faq/
- [G3] Oracle, *Always Free Resources* (12/06/2026) : https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- [G4] Oracle, *Regions and Availability Domains* (22/06/2026) : https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm
- [G5] Oracle, *Creating an Instance* (13/10/2026) : https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm
- [G6] Oracle, *Updating a Security List* (25/06/2025) : https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/update-securitylist.htm
- [G7] Oracle, tutoriel *Apache and PHP on Ubuntu* (règle d'entrée, iptables) : https://docs.oracle.com/en-us/iaas/developer-tutorials/tutorials/apache-on-ubuntu/01oci-ubuntu-apache-summary.htm
- [G8] Oracle, *Oracle-Provided Images* (pare-feu par défaut, UFW) : https://docs.oracle.com/en-us/iaas/Content/Compute/References/images.htm
- [G9] Oracle Developers Blog, M. Bach, *Enabling network traffic to Ubuntu images in Oracle Cloud Infrastructure* (04/07/2022) : https://blogs.oracle.com/developers/post/enabling-network-traffic-to-ubuntu-images-in-oracle-cloud-infrastructure
- [G10] Oracle, *Identity Domains With the "Security Policy for OCI Console" Sign-On Policy* (MFA, 07/10/2025) : https://docs.oracle.com/iaas/Content/Security/Reference/iam_security_topic-iam_mfa_identity_domains_signon_policy.htm
- [G11] Source secondaire : inithtml, *Oracle Cloud Free Tier: Sign Up and Deploy a Free Ubuntu 24.04 VPS* (20/09/2026) : https://en.inithtml.com/resources/oracle-cloud-free-tier-sign-up-and-deploy-a-free-ubuntu-24-04-vps/
- [G12] Source secondaire : RackUpIt, *Open Ports 80 & 443 on Oracle Cloud VPS* (12/07/2026) : https://www.rackupit.com/blog/open-port-80-443-oracle-cloud-vps
- [G13] GitHub Docs, *Generating a new SSH key and adding it to the ssh-agent* : https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent
- [G14] Microsoft Learn, *Key-based authentication in OpenSSH for Windows* : https://learn.microsoft.com/windows-server/administration/openssh/openssh_keymanagement
- [G15] Microsoft Learn, *Get started with OpenSSH for Windows* : https://learn.microsoft.com/windows-server/administration/openssh/openssh_install_firstuse
- [G16] DuckDNS, *spec* et *FAQ* : https://www.duckdns.org/spec.jsp, https://www.duckdns.org/faqs.jsp
- [G17] Docker, *Install Docker Engine on Ubuntu* (dépôt officiel, utilisé par le script) : https://docs.docker.com/engine/install/ubuntu/
- [G18] Ubuntu Server, *Automatic updates* : https://ubuntu.com/server/docs/how-to/software/automatic-updates/
- [G19] GitHub Docs, *Configuring a publishing source for your GitHub Pages site* : https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- [G20] OTP 2.10.0, *GTFS GraphQL API* (point d'entrée `/otp/gtfs/v1`) : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/apis/GTFS-GraphQL-API.md
- [G21] OTP 2.10.0, *Actuator API* : https://github.com/opentripplanner/OpenTripPlanner/blob/v2.10.0/doc/user/sandbox/ActuatorAPI.md

## Ce qu'il faut retenir

- Ce soir : un compte Oracle, une machine gratuite de 2 processeurs et 12 Go, deux ports ouverts dans la console, un sous-domaine DuckDNS, puis **une seule commande** sur le serveur.
- La région d'origine est définitive : Frankfurt est conseillée, car elle offre trois chances quand Oracle manque de machines.
- Le jeton DuckDNS et la clé SSH privée sont des secrets : le jeton ne se colle que dans le terminal du serveur, quand le script le demande.
- Seules l'API et deux petits fichiers sont publics ; tout le reste répond « Not found ».
- Après ce soir, tout se met à jour seul. Il suffit de se connecter à la console Oracle une fois par mois.
