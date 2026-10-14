#!/usr/bin/env bash
# Toulouse Demain: install the server on a fresh Ubuntu 24.04 ARM64 machine
# (Oracle Cloud Always Free, VM.Standard.A1.Flex). Guide: docs/guide-serveur-oracle.md
#
# Usage, on the server, logged in with your usual account (ubuntu on Oracle):
#   curl -fsSLO https://raw.githubusercontent.com/CyprienBethe/toulouse-demain/main/deploy/bootstrap.sh && sudo bash bootstrap.sh
#
# Idempotent: every step checks what is already done, so the script can be run
# again at any time (after a failure, or after `git pull` to apply changes).
#
# Steps:
#   1. clone (or update) the repository in ~/toulouse-demain;
#   2. create deploy/.env, ASKING for the DuckDNS subdomain and token (hidden
#      input; never a command-line argument, never printed), and point the
#      subdomain to this server;
#   3. automatic security updates (unattended-upgrades);
#   4. SSH: keys only, password login disabled (the current session stays open);
#   5. local firewall: ports 80 and 443 opened, persistently;
#   6. Docker Engine and the Compose plugin, from Docker's official repository;
#   7. download the latest graph (update-graph.sh), then docker compose up -d;
#   8. systemd timers: weekly graph update, DuckDNS refresh;
#   9. checks, then what to put in site/config.js.
#
# Optional environment variables, after sudo (no secret goes through them),
# e.g. `sudo TD_BRANCH=sprint-1 bash bootstrap.sh`:
#   TD_REPO_URL, TD_BRANCH: repository and branch to clone (default: main of
#   CyprienBethe/toulouse-demain); TD_USER: account that owns the installation
#   (default: the one that ran sudo).
set -Eeuo pipefail

REPO_URL=${TD_REPO_URL:-https://github.com/CyprienBethe/toulouse-demain.git}
BRANCH=${TD_BRANCH:-main}
# Docker's apt signing key (docs.docker.com, key in use since 2017).
DOCKER_GPG_FINGERPRINT=9DC858229FC7DD38854AE2D88D81803C0EBFCD88
LOG=/var/log/toulouse-demain-bootstrap.log

# ---------------------------------------------------------------- messages
say() { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\n    ATTENTION : %s\n\n' "$*" >&2; }
die() {
  printf '\nERREUR : %s\n' "$*" >&2
  printf 'Une fois le problème réglé, relance la même commande : sudo bash bootstrap.sh\n' >&2
  printf '(les étapes déjà faites seront sautées).\n' >&2
  exit 1
}
on_error() {
  # Reported once, by the main shell (not by each subshell on the way up).
  if ((BASH_SUBSHELL > 0)); then
    return 0
  fi
  # The command text is not printed: it could contain a value typed by the user.
  printf '\nERREUR inattendue à la ligne %s de bootstrap.sh.\n' "$1" >&2
  printf 'Les détails techniques sont dans %s (fin du fichier : sudo tail -n 30 %s).\n' "$LOG" "$LOG" >&2
  printf 'Relance la même commande : sudo bash bootstrap.sh (les étapes déjà faites seront sautées).\n' >&2
}

# ---------------------------------------------------------------- helpers
run_as_user() { sudo -u "$TARGET_USER" -H -- "$@"; }

apt_get() {
  # Waits up to 10 minutes if another apt (first boot, daily updates) holds the lock.
  if ! DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=600 -y -q "$@" >>"$LOG" 2>&1; then
    tail -n 15 "$LOG" >&2
    die "apt-get $1 a échoué (détails ci-dessus et dans $LOG). Souvent un souci réseau passager."
  fi
}

# Value of KEY in an env file (quotes removed), empty if absent.
env_value() { sed -n "s/^$2=//p" "$1" | tr -d '"' | tail -n 1; }

# Set KEY=VALUE in an env file, in pure bash: the value (possibly a secret)
# never appears on a command line. The file keeps its owner and mode 600.
set_env_value() {
  local file=$1 key=$2 value=$3 tmp line found=false
  tmp=$(mktemp "$(dirname "$file")/.env.XXXXXX")
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "$key="* ]]; then
      if [[ "$found" == false ]]; then
        printf '%s=%s\n' "$key" "$value" >>"$tmp"
        found=true
      fi
    else
      printf '%s\n' "$line" >>"$tmp"
    fi
  done <"$file"
  if [[ "$found" == false ]]; then
    printf '%s=%s\n' "$key" "$value" >>"$tmp"
  fi
  chmod 600 "$tmp"
  chown --reference="$file" "$tmp"
  mv -f "$tmp" "$file"
}

# Normalize what the user typed as subdomain: "https://Abc.duckdns.org/" -> "abc".
normalize_subdomain() {
  local s=${1,,}
  s=${s//[[:space:]]/}
  s=${s#http://}
  s=${s#https://}
  s=${s%/}
  s=${s%.duckdns.org}
  printf '%s' "$s"
}
valid_subdomain() { [[ "$1" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; }
# DuckDNS tokens look like UUIDs; only the characters are checked here
# (DuckDNS itself says whether the token is right).
valid_token() { [[ "$1" =~ ^[A-Za-z0-9-]{20,64}$ ]]; }

ask() {
  local reply
  printf '%s' "$1" >/dev/tty
  IFS= read -r reply </dev/tty || die "impossible de lire la réponse au clavier"
  printf '%s' "$reply"
}
ask_secret() {
  local reply
  printf '%s' "$1" >/dev/tty
  IFS= read -r -s reply </dev/tty || die "impossible de lire la réponse au clavier"
  printf '\n' >/dev/tty
  printf '%s' "$reply"
}
ask_yes() {
  local reply
  reply=$(ask "$1")
  [[ -z "$reply" || "${reply,,}" =~ ^(o|oui|y|yes)$ ]]
}

# Insert RULE in the *filter table of an iptables-save file, before the first
# INPUT rule that rejects or drops (Oracle's images end INPUT with a REJECT).
insert_rule_in_file() {
  local file=$1 rule=$2 tmp line in_filter=false inserted=false
  tmp=$(mktemp "${file}.XXXXXX")
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "*filter" ]]; then
      in_filter=true
    fi
    if [[ "$in_filter" == true && "$inserted" == false ]]; then
      if [[ "$line" =~ ^-A\ INPUT\ .*-j\ (REJECT|DROP) || "$line" == COMMIT ]]; then
        printf '%s\n' "$rule" >>"$tmp"
        inserted=true
      fi
    fi
    if [[ "$line" == COMMIT ]]; then
      in_filter=false
    fi
    printf '%s\n' "$line" >>"$tmp"
  done <"$file"
  if [[ "$inserted" == false ]]; then
    rm -f "$tmp"
    return 1
  fi
  chmod --reference="$file" "$tmp"
  mv -f "$tmp" "$file"
}

# Position for `iptables -I INPUT`: just before the first REJECT/DROP rule.
input_insert_position() {
  local n
  n=$(iptables -L INPUT --line-numbers -n | sed -n -E 's/^([0-9]+) +(REJECT|DROP) .*/\1/p' | head -n 1)
  printf '%s' "${n:-1}"
}

# Heap and container limit for OTP, from the RAM of the machine (measured in
# CI: 1.2 GB used by the loaded server, live heap under 0.9 GB).
memory_settings() {
  local kib=$1
  if ((kib >= 10 * 1024 * 1024)); then
    printf '6g 8g'
  elif ((kib >= 4718592)); then # 4.5 GiB
    printf '3g 4g'
  else
    printf '2g 3g'
  fi
}

check_api() {
  # Through Caddy and its certificate, without leaving the machine.
  curl -fsS --max-time 15 --resolve "$1:443:127.0.0.1" -H 'Content-Type: application/json' \
    -d '{"query":"{ feeds { feedId } }"}' "https://$1/otp/gtfs/v1" 2>/dev/null
}

# ---------------------------------------------------------------- steps
preflight() {
  if [[ $EUID -ne 0 ]]; then
    die "lance ce script avec sudo : sudo bash bootstrap.sh"
  fi
  TARGET_USER=${TD_USER:-${SUDO_USER:-}}
  if [[ -z "$TARGET_USER" || "$TARGET_USER" == root ]]; then
    die "lance-le depuis ton compte habituel (ubuntu sur Oracle) avec sudo, pas directement en root"
  fi
  TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
  if [[ -z "$TARGET_HOME" || ! -d "$TARGET_HOME" ]]; then
    die "compte $TARGET_USER introuvable"
  fi
  TARGET_GROUP=$(id -gn "$TARGET_USER")
  REPO_DIR="$TARGET_HOME/toulouse-demain"
  DEPLOY_DIR="$REPO_DIR/deploy"
  ENV_FILE="$DEPLOY_DIR/.env"
  if ! { : </dev/tty; } 2>/dev/null; then
    die "ce script pose des questions : lance-le dans un terminal (ta session SSH)"
  fi
  touch "$LOG"
  chmod 600 "$LOG"
  printf '\n===== %s bootstrap.sh\n' "$(date -u +%FT%TZ)" >>"$LOG"

  # shellcheck source=/dev/null
  . /etc/os-release
  OS_ID=$ID
  OS_CODENAME=${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}
  case "$OS_ID" in
    ubuntu) ;;
    debian) warn "système Debian ($PRETTY_NAME) : prévu pour Ubuntu 24.04, on continue." ;;
    *) die "système non pris en charge : $PRETTY_NAME (attendu : Ubuntu 24.04)" ;;
  esac
  if [[ "$OS_ID" == ubuntu && "${VERSION_ID:-}" != 24.04 ]]; then
    warn "prévu pour Ubuntu 24.04, ici $PRETTY_NAME : on continue quand même."
  fi
  local arch
  arch=$(dpkg --print-architecture)
  if [[ "$arch" != arm64 ]]; then
    info "processeur $arch (prévu : arm64). Les images Docker existent aussi pour $arch : on continue."
  fi
  info "compte : $TARGET_USER ; dossier : $REPO_DIR ; journal : $LOG"
}

wait_first_boot() {
  if command -v cloud-init >/dev/null 2>&1; then
    info "attente de la fin du premier démarrage de la machine (cloud-init)..."
    cloud-init status --wait >>"$LOG" 2>&1 || true
  fi
}

clone_repo() {
  say "1/9 Dépôt toulouse-demain"
  if ! command -v git >/dev/null 2>&1; then
    apt_get update
    apt_get install git
  fi
  if [[ -d "$REPO_DIR/.git" ]]; then
    if run_as_user git -C "$REPO_DIR" pull --ff-only --quiet >>"$LOG" 2>&1; then
      info "déjà présent, mis à jour (git pull)"
    else
      warn "git pull impossible (modifications locales ?) : on garde la version présente."
    fi
  elif [[ -e "$REPO_DIR" ]]; then
    die "$REPO_DIR existe mais n'est pas un dépôt git : renomme-le (mv) puis relance"
  else
    run_as_user git clone --quiet --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
    info "cloné dans $REPO_DIR"
  fi
  info "version : $(run_as_user git -C "$REPO_DIR" log -1 --format='%h %s')"
}

update_duckdns() {
  # Prints "DuckDNS answer ...: OK <ip> UPDATED"; fails on KO or network error.
  run_as_user bash "$DEPLOY_DIR/duckdns-update.sh"
}

configure_env() {
  say "2/9 Sous-domaine DuckDNS et fichier deploy/.env"
  if [[ ! -f "$ENV_FILE" ]]; then
    install -o "$TARGET_USER" -g "$TARGET_GROUP" -m 600 "$DEPLOY_DIR/.env.example" "$ENV_FILE"
    local kib heap limit
    kib=$(sed -n 's/^MemTotal: *\([0-9]*\) kB$/\1/p' /proc/meminfo)
    read -r heap limit <<<"$(memory_settings "$kib")"
    set_env_value "$ENV_FILE" OTP_JAVA_OPTS "\"-Xms$heap -Xmx$heap -XX:+AlwaysPreTouch\""
    set_env_value "$ENV_FILE" OTP_MEM_LIMIT "$limit"
    info "créé à partir de .env.example ; mémoire $((kib / 1024)) Mo : tas Java $heap, limite $limit"
  fi
  chown "$TARGET_USER:$TARGET_GROUP" "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  local subdomain token attempt answer
  subdomain=$(env_value "$ENV_FILE" DUCKDNS_SUBDOMAIN)
  token=$(env_value "$ENV_FILE" DUCKDNS_TOKEN)
  if [[ -n "$subdomain" && -n "$token" ]] \
    && ask_yes "    Garder le sous-domaine déjà enregistré « ${subdomain}.duckdns.org » et son jeton ? [O/n] "; then
    set_env_value "$ENV_FILE" API_DOMAIN "${subdomain}.duckdns.org"
    update_duckdns || die "DuckDNS refuse le jeton enregistré : relance et réponds « n » pour le saisir à nouveau"
    return 0
  fi

  info "Sur https://www.duckdns.org (connecté), tu vois ton jeton (« token ») et ton sous-domaine."
  info "Le jeton est un secret : colle-le ici seulement, nulle part ailleurs."
  for attempt in 1 2 3; do
    while :; do
      # Two statements: a failed read (Ctrl-D) then stops the script instead of looping.
      answer=$(ask "    Sous-domaine (ce qui précède .duckdns.org) : ")
      subdomain=$(normalize_subdomain "$answer")
      valid_subdomain "$subdomain" && break
      info "« $subdomain » n'est pas un nom valide (lettres minuscules, chiffres et tirets). Recommence."
    done
    while :; do
      token=$(ask_secret "    Jeton DuckDNS (rien ne s'affiche quand tu colles, c'est normal) : ")
      token=${token//[[:space:]]/}
      valid_token "$token" && break
      info "Ce n'est pas un jeton DuckDNS (format attendu : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx). Recommence."
    done
    info "jeton reçu (${#token} caractères, non affiché)"
    set_env_value "$ENV_FILE" DUCKDNS_SUBDOMAIN "$subdomain"
    set_env_value "$ENV_FILE" DUCKDNS_TOKEN "$token"
    set_env_value "$ENV_FILE" API_DOMAIN "${subdomain}.duckdns.org"
    if update_duckdns; then
      info "${subdomain}.duckdns.org pointe maintenant vers ce serveur"
      return 0
    fi
    warn "DuckDNS a refusé (essai $attempt sur 3) : sous-domaine absent de ton compte, ou jeton incomplet."
  done
  die "DuckDNS a refusé trois fois. Vérifie sur https://www.duckdns.org que le sous-domaine existe et recopie le jeton en entier."
}

enable_security_updates() {
  say "3/9 Mises à jour de sécurité automatiques"
  apt_get update
  apt_get install ca-certificates curl gnupg unattended-upgrades
  printf '%s\n' 'APT::Periodic::Update-Package-Lists "1";' 'APT::Periodic::Unattended-Upgrade "1";' \
    >/etc/apt/apt.conf.d/20auto-upgrades
  systemctl enable --now apt-daily.timer apt-daily-upgrade.timer >>"$LOG" 2>&1
  info "actives : correctifs de sécurité d'Ubuntu installés chaque jour (sans redémarrage automatique)"
}

harden_ssh() {
  say "4/9 SSH : connexion par clé uniquement"
  local keys="$TARGET_HOME/.ssh/authorized_keys" conf=/etc/ssh/sshd_config.d/10-toulouse-demain.conf want
  if ! grep -qE '(ssh-(ed25519|rsa)|ecdsa-sha2-|sk-(ssh|ecdsa)-)' "$keys" 2>/dev/null; then
    warn "aucune clé SSH dans $keys : la connexion par mot de passe reste active, pour ne pas te bloquer dehors."
    return 0
  fi
  # sshd keeps the first value read and reads sshd_config.d/ in alphabetical
  # order: 10-... wins over the image's own files (50-cloud-init.conf...).
  want=$'# Written by toulouse-demain deploy/bootstrap.sh: SSH keys only.\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no'
  if [[ "$(cat "$conf" 2>/dev/null)" == "$want" ]]; then
    info "déjà fait"
    return 0
  fi
  printf '%s\n' "$want" >"$conf"
  chmod 644 "$conf"
  if ! sshd -t >>"$LOG" 2>&1; then
    rm -f "$conf"
    warn "sshd refuse la nouvelle configuration : SSH laissé tel quel (détails dans $LOG)."
    return 0
  fi
  # reload, not restart: open sessions (yours) are kept.
  if systemctl is-active --quiet ssh.service; then
    systemctl reload ssh.service
  fi
  info "mot de passe refusé, clé obligatoire ; ta session actuelle reste ouverte"
}

open_firewall() {
  say "5/9 Pare-feu local : ports 80 et 443"
  local rules=/etc/iptables/rules.v4 port rule
  if [[ -f "$rules" ]]; then
    # Oracle's Ubuntu images: iptables rules restored at boot from rules.v4,
    # SSH only, then REJECT. Docs: do not use ufw on these images.
    # The file is edited directly (not `netfilter-persistent save`, which would
    # also save Docker's own rules); the live rules get the same lines.
    if [[ ! -f "$rules.before-toulouse-demain" ]]; then
      cp -p "$rules" "$rules.before-toulouse-demain"
    fi
    for port in 80 443; do
      rule="-A INPUT -p tcp -m state --state NEW -m tcp --dport $port -j ACCEPT"
      if ! grep -qxF -- "$rule" "$rules"; then
        insert_rule_in_file "$rules" "$rule" || die "impossible d'ajouter le port $port dans $rules"
      fi
      if ! iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT 2>/dev/null; then
        iptables -I INPUT "$(input_insert_position)" -p tcp -m state --state NEW -m tcp --dport "$port" -j ACCEPT
      fi
    done
    if ! systemctl is-enabled --quiet netfilter-persistent.service 2>/dev/null; then
      warn "netfilter-persistent n'est pas actif : les règles de $rules risquent de ne pas être rechargées au démarrage."
    fi
    info "ouverts maintenant et après redémarrage ($rules ; copie d'origine : $rules.before-toulouse-demain)"
  elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
    ufw allow 80/tcp >>"$LOG"
    ufw allow 443/tcp >>"$LOG"
    info "ouverts dans ufw"
  else
    info "aucun pare-feu local actif (ni $rules, ni ufw) : rien à ouvrir sur la machine"
  fi
  info "rappel : les ports 80 et 443 doivent AUSSI être ouverts dans la liste de sécurité Oracle (guide, étape 4)"
}

install_docker() {
  say "6/9 Docker Engine et Docker Compose (dépôt officiel de Docker)"
  local pkg conflicts=() key=/etc/apt/keyrings/docker.asc tmpkey gpg_home
  for pkg in docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc; do
    # shellcheck disable=SC2016  # ${Status} is a dpkg-query field, not a shell variable
    if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
      conflicts+=("$pkg")
    fi
  done
  if ((${#conflicts[@]})); then
    info "retrait des paquets incompatibles : ${conflicts[*]}"
    apt_get remove "${conflicts[@]}"
  fi
  # An older docker.list would conflict with docker.sources (Signed-By).
  if [[ -f /etc/apt/sources.list.d/docker.list ]] && grep -q download.docker.com /etc/apt/sources.list.d/docker.list; then
    mv /etc/apt/sources.list.d/docker.list /etc/apt/sources.list.d/docker.list.disabled
  fi

  install -m 0755 -d /etc/apt/keyrings
  tmpkey=$(mktemp)
  curl -fsSL --retry 3 "https://download.docker.com/linux/${OS_ID}/gpg" -o "$tmpkey"
  if command -v gpg >/dev/null 2>&1; then
    gpg_home=$(mktemp -d)
    if ! GNUPGHOME=$gpg_home gpg --batch --show-keys --with-colons "$tmpkey" 2>/dev/null \
      | grep -qE "^fpr:+${DOCKER_GPG_FINGERPRINT}:"; then
      rm -rf "$gpg_home" "$tmpkey"
      die "la clé de signature téléchargée chez Docker n'a pas l'empreinte attendue ($DOCKER_GPG_FINGERPRINT). Arrêt par sécurité : préviens l'équipe."
    fi
    rm -rf "$gpg_home"
  fi
  install -m 0644 "$tmpkey" "$key"
  rm -f "$tmpkey"
  printf '%s\n' "Types: deb" "URIs: https://download.docker.com/linux/${OS_ID}" "Suites: ${OS_CODENAME}" \
    "Components: stable" "Architectures: $(dpkg --print-architecture)" "Signed-By: $key" \
    >/etc/apt/sources.list.d/docker.sources
  apt_get update
  apt_get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now containerd.service docker.service >>"$LOG" 2>&1
  if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx docker; then
    usermod -aG docker "$TARGET_USER"
  fi
  info "$(docker --version) ; $(docker compose version)"
}

start_services() {
  say "7/9 Graphe et démarrage d'OpenTripPlanner et de Caddy"
  info "téléchargement du dernier graphe publié par GitHub Actions, puis chargement (quelques minutes)"
  if ! run_as_user bash "$DEPLOY_DIR/update-graph.sh" 2>&1 | tee -a "$LOG"; then
    die "téléchargement ou chargement du graphe en échec (message ci-dessus). Une construction en cours sur GitHub ? Réessaie dans 10 minutes."
  fi
  info "construction de l'image Caddy et démarrage (3 à 10 minutes la première fois)"
  if ! (cd "$DEPLOY_DIR" && run_as_user docker compose up -d --build) 2>&1 | tee -a "$LOG"; then
    die "docker compose up a échoué (message ci-dessus)"
  fi
  # A changed Caddyfile (after git pull) is applied without cutting connections.
  if ! (cd "$DEPLOY_DIR" && run_as_user docker compose exec -T caddy \
    caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile) >>"$LOG" 2>&1; then
    info "rechargement de Caddy ignoré (il vient de démarrer avec la configuration à jour)"
  fi
}

install_timers() {
  say "8/9 Tâches automatiques (minuteurs systemd)"
  local dir=/etc/systemd/system
  printf '%s\n' \
    "[Unit]" \
    "Description=Toulouse Demain : téléchargement du dernier graphe OTP" \
    "Documentation=https://github.com/CyprienBethe/toulouse-demain/blob/main/docs/guide-serveur-oracle.md" \
    "Wants=network-online.target" \
    "After=network-online.target docker.service" \
    "Requires=docker.service" \
    "" \
    "[Service]" \
    "Type=oneshot" \
    "User=$TARGET_USER" \
    "SupplementaryGroups=docker" \
    "WorkingDirectory=$DEPLOY_DIR" \
    "ExecStart=/bin/bash $DEPLOY_DIR/update-graph.sh" \
    "TimeoutStartSec=45min" \
    "NoNewPrivileges=yes" \
    "PrivateTmp=yes" \
    "ProtectSystem=full" \
    >"$dir/toulouse-demain-graph.service"
  printf '%s\n' \
    "[Unit]" \
    "Description=Toulouse Demain : graphe chaque lundi, après sa construction en CI (03:17 UTC)" \
    "" \
    "[Timer]" \
    "OnCalendar=Mon *-*-* 06:30:00 UTC" \
    "RandomizedDelaySec=20min" \
    "Persistent=true" \
    "" \
    "[Install]" \
    "WantedBy=timers.target" \
    >"$dir/toulouse-demain-graph.timer"
  printf '%s\n' \
    "[Unit]" \
    "Description=Toulouse Demain : sous-domaine DuckDNS vers l'adresse IP du serveur" \
    "Wants=network-online.target" \
    "After=network-online.target" \
    "" \
    "[Service]" \
    "Type=oneshot" \
    "User=$TARGET_USER" \
    "ExecStart=/bin/bash $DEPLOY_DIR/duckdns-update.sh" \
    "NoNewPrivileges=yes" \
    "PrivateTmp=yes" \
    "ProtectSystem=strict" \
    "ProtectHome=read-only" \
    >"$dir/toulouse-demain-duckdns.service"
  printf '%s\n' \
    "[Unit]" \
    "Description=Toulouse Demain : DuckDNS toutes les 30 minutes" \
    "" \
    "[Timer]" \
    "OnBootSec=2min" \
    "OnUnitActiveSec=30min" \
    "RandomizedDelaySec=1min" \
    "" \
    "[Install]" \
    "WantedBy=timers.target" \
    >"$dir/toulouse-demain-duckdns.timer"
  systemctl daemon-reload
  systemctl enable --now toulouse-demain-graph.timer toulouse-demain-duckdns.timer >>"$LOG" 2>&1
  info "graphe : chaque lundi vers 06:30 UTC ; DuckDNS : toutes les 30 minutes"
  info "état : systemctl list-timers 'toulouse-demain-*' ; journaux : journalctl -u toulouse-demain-graph"
}

final_checks() {
  say "9/9 Vérifications"
  local domain answer status dns i
  domain=$(env_value "$ENV_FILE" API_DOMAIN)

  for i in $(seq 1 60); do
    if curl -fsS -o /dev/null http://127.0.0.1:8080/otp/actuators/health 2>/dev/null; then
      break
    fi
    if ((i == 60)); then
      die "OpenTripPlanner ne répond pas après 5 minutes. Regarde : cd $DEPLOY_DIR && sudo docker compose logs --tail 50 otp"
    fi
    sleep 5
  done
  info "OpenTripPlanner : graphe chargé"

  dns=$(getent ahostsv4 "$domain" | head -n 1 | cut -d' ' -f1 || true)
  info "DNS : $domain -> ${dns:-(pas encore de réponse)}"

  info "certificat HTTPS : Caddy le demande à Let's Encrypt (jusqu'à 3 minutes)..."
  answer=""
  for i in $(seq 1 18); do
    if answer=$(check_api "$domain") && [[ "$answer" == *feedId* ]]; then
      break
    fi
    answer=""
    sleep 10
  done
  if [[ -z "$answer" ]]; then
    cat >&2 <<EOF

    Le certificat HTTPS n'est pas encore obtenu. Causes probables, dans l'ordre :
    1. ports 80 et 443 pas encore ouverts dans la liste de sécurité Oracle (guide, étape 4) ;
    2. $domain ne pointe pas vers l'adresse IP publique du serveur (ligne DNS ci-dessus) ;
    3. il faut juste attendre un peu : Caddy réessaie tout seul.
    Messages de Caddy : cd $DEPLOY_DIR && sudo docker compose logs --tail 30 caddy
    Après correction : cd $DEPLOY_DIR && sudo docker compose restart caddy
EOF
    die "API pas encore joignable en HTTPS"
  fi
  info "API en HTTPS : OK ($answer)"

  status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 --resolve "$domain:443:127.0.0.1" \
    "https://$domain/otp/actuators/health" || true)
  if [[ "$status" == 404 ]]; then
    info "interface de débogage et API internes d'OTP : bien cachées (404)"
  else
    warn "https://$domain/otp/actuators/health répond $status au lieu de 404 : préviens l'équipe."
  fi

  say "Terminé !"
  info "Adresse de l'API : https://$domain/otp/gtfs/v1"
  info ""
  info "Ligne à mettre dans site/config.js :"
  info ""
  info "    export const API_BASE_URL = \"https://$domain\";"
  info ""
  info "Vérification depuis ton ordinateur (Terminal sur macOS ou Linux) :"
  info "    curl -s https://$domain/otp/gtfs/v1 -H 'Content-Type: application/json' -d '{\"query\":\"{ feeds { feedId } }\"}'"
  info "Réponse attendue : {\"data\":{\"feeds\":[...]}} avec tisseo, sncf et futur (dans n'importe quel ordre)."
  info "Windows : commande PowerShell dans le guide, étape 7."
  info ""
  info "Pour utiliser docker sans sudo, déconnecte-toi (exit) puis reconnecte-toi."
  if [[ -f /var/run/reboot-required ]]; then
    info "Ubuntu demande un redémarrage (mises à jour) : sudo reboot. Tout redémarre seul en 2 minutes environ."
  fi
}

main() {
  say "Installation du serveur Toulouse Demain"
  preflight
  info "Deux questions au début (sous-domaine et jeton DuckDNS), puis 10 à 20 minutes sans rien faire."
  wait_first_boot
  clone_repo
  configure_env
  enable_security_updates
  harden_ssh
  open_firewall
  install_docker
  start_services
  install_timers
  final_checks
}

# Run only when executed (sourcing it gives access to the functions, for tests).
# On one line, so that a `git pull` that rewrites this file during the run is harmless.
if [[ "${BASH_SOURCE[0]:-$0}" == "$0" ]]; then trap 'on_error "$LINENO"' ERR; main "$@"; exit $?; fi
