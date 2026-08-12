#!/bin/bash
#
# Initial setup for a fresh Ubuntu server. Run once, as root:
#   bash initial_server_setup.sh
#
# What it does:
#   1. Creates a sudo user and moves root's SSH keys to it
#   2. Hardens sshd (no root login, no password auth) — but only after
#      verifying the new user actually has a key, so you can't be locked out
#   3. Enables UFW (SSH, 80, 443)
#   4. Installs Docker + the Compose v2 plugin, fail2ban, unattended-upgrades
#   5. Adds a 2G swapfile (Postgres + docker build on a small VPS need it)
#
# NOTE: Docker publishes ports by writing iptables rules AHEAD of UFW, so UFW
# does not protect published container ports. Keep compose port mappings bound
# to 127.0.0.1 (as backend/docker-compose.yaml does) and let the reverse proxy
# on 80/443 be the only public entry point.

set -euo pipefail

USERNAME=sourabh
COPY_AUTHORIZED_KEYS_FROM_ROOT=true

# ---- Sudo user ---------------------------------------------------------
useradd --create-home --shell /bin/bash --groups sudo "${USERNAME}"

encrypted_root_pw="$(grep '^root:' /etc/shadow | cut --delimiter=: --fields=2)"
if [ "${encrypted_root_pw}" != "*" ]; then
    # Transfer the auto-generated root password to the new user and lock
    # root out of password-based access.
    echo "${USERNAME}:${encrypted_root_pw}" | chpasswd --encrypted
    passwd --lock root
else
    # Key-based image: clear the placeholder so a new password can be set
    # without knowing a previous one.
    passwd --delete "${USERNAME}"
fi

# Force a password change on first login (sudo needs one).
chage --lastday 0 "${USERNAME}"

home_directory="$(eval echo "~${USERNAME}")"
mkdir --parents "${home_directory}/.ssh"

if [ "${COPY_AUTHORIZED_KEYS_FROM_ROOT}" = true ]; then
    cp /root/.ssh/authorized_keys "${home_directory}/.ssh"
fi

chmod 0700 "${home_directory}/.ssh"
chmod 0600 "${home_directory}/.ssh/authorized_keys"
chown --recursive "${USERNAME}":"${USERNAME}" "${home_directory}/.ssh"

# ---- SSH hardening -----------------------------------------------------
# Refuse to disable password auth if the new user has no key — otherwise the
# rest of this script would lock everyone out of the box.
if [ ! -s "${home_directory}/.ssh/authorized_keys" ]; then
    echo "ERROR: ${home_directory}/.ssh/authorized_keys is missing or empty." >&2
    echo "Add a public key for ${USERNAME} and re-run from this point." >&2
    exit 1
fi

sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
# Cloud images ship drop-in overrides that would silently win over the edits
# above — pin ours last.
if [ -d /etc/ssh/sshd_config.d ]; then
    printf 'PermitRootLogin no\nPasswordAuthentication no\n' \
        > /etc/ssh/sshd_config.d/99-hardening.conf
fi
# Keepalive: probe idle clients every 60s so NAT routers don't silently drop
# the connection; give up only after ~5min of no response.
printf 'ClientAliveInterval 60\nClientAliveCountMax 5\n' \
    > /etc/ssh/sshd_config.d/98-keepalive.conf
sshd -t
systemctl restart ssh 2>/dev/null || systemctl restart sshd

# ---- Firewall ----------------------------------------------------------
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ---- Packages ----------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes ca-certificates curl git tmux fail2ban unattended-upgrades
systemctl enable --now fail2ban

# Docker (get.docker.com installs the Compose v2 plugin as well — no separate
# docker-compose binary needed; the command is `docker compose`).
curl -fsSL https://get.docker.com | sh
usermod -aG docker "${USERNAME}"   # takes effect on next login

# ---- Swap --------------------------------------------------------------
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ---- Verify ------------------------------------------------------------
docker --version
docker compose version

echo
echo "Done. Next steps:"
echo "  1. In a NEW terminal, confirm you can SSH in:  ssh ${USERNAME}@<server-ip>"
echo "     (first login asks you to set a password — that becomes your sudo password)"
echo "  2. git clone the repo, copy backend/.env.example to backend/.env and fill it in"
echo "     (set a real POSTGRES_PASSWORD before the first 'up')"
echo "  3. cd backend && docker compose -f docker-compose.yaml up -d --build"
