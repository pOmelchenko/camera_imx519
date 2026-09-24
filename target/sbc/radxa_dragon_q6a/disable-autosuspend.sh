#!/usr/bin/env bash
# Disable GNOME automatic suspend on AC power for GDM and radxa. Requires sudo.
# Keeps screen blanking and manual suspend; writes a rollback script first.
set -euo pipefail
(( EUID == 0 )) || { echo 'Run: sudo bash ~/camera-imx519/disable-autosuspend.sh' >&2; exit 1; }
schema=org.gnome.settings-daemon.plugins.power
key=sleep-inactive-ac-type
backup_dir="$(mktemp -d /var/backups/imx519-autosuspend.XXXXXXXX)"
rollback="$backup_dir/restore.sh"
printf '#!/usr/bin/env bash\nset -euo pipefail\n' > "$rollback"
for account in gdm radxa; do
    account_uid="$(id -u "$account")"
    if [[ -S "/run/user/$account_uid/bus" ]]; then
        settings=(runuser -u "$account" -- env "XDG_RUNTIME_DIR=/run/user/$account_uid"
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$account_uid/bus" gsettings)
    else
        settings=(runuser -u "$account" -- dbus-run-session -- gsettings)
    fi
    old_value="$("${settings[@]}" get "$schema" "$key")"
    printf '%q ' "${settings[@]}" set "$schema" "$key" "$old_value" >> "$rollback"
    printf '\n' >> "$rollback"
    "${settings[@]}" set "$schema" "$key" nothing
    new_value="$("${settings[@]}" get "$schema" "$key")"
    [[ "$new_value" == "'nothing'" ]] || { echo "Verification failed for $account" >&2; exit 1; }
    printf '%s: %s -> %s\n' "$account" "$old_value" "$new_value"
done
chmod 700 "$rollback"
printf 'Rollback: sudo bash %s\n' "$rollback"
