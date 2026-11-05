#!/usr/bin/env bash
set -euo pipefail

# Load the image's normal X11 behavior with a browser menu for this stack.
# Keep the generated configuration outside the persistent profile volume.
config_dir=$(mktemp -d /tmp/camofox-openbox.XXXXXX)
export XDG_CONFIG_HOME="$config_dir"
mkdir "$config_dir/openbox"
config="$config_dir/openbox/rc.xml"
menu="$config_dir/openbox/menu.xml"
trap 'rm -f -- "$config" "$menu"; rmdir -- "$config_dir/openbox" "$config_dir"' EXIT
cp /opt/camofox-desktop/menu.xml "$menu"
sed -e 's|<menu>root-menu</menu>|<menu>camofox-root-menu</menu>|g' \
  -e '/^<keyboard>/a\  <keybind key="C-A-b"><action name="Execute"><command>/bin/bash /opt/camofox-desktop/open-browser.sh</command></action></keybind>' \
  /etc/xdg/openbox/rc.xml > "$config"
# The image's Openbox autostart launches a full-screen terminal. Leave the
# desktop idle until someone opens a browser or an automation job starts.
xsetroot -solid '#202832'
dbus-launch --exit-with-session /usr/bin/openbox --config-file "$config"
