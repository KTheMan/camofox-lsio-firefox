#!/usr/bin/env bash
set -euo pipefail

render_config() {
  sed -e 's|<menu>root-menu</menu>|<menu>camofox-root-menu</menu>|g' \
    -e '/^<keyboard>/a\  <keybind key="C-A-b"><action name="Execute"><command>/bin/bash /opt/camofox-desktop/open-browser.sh</command></action></keybind>' \
    -e '/^<\/applications>/i\  <application name="camofox-launcher">\n    <decor>no</decor>\n    <focus>no</focus>\n    <layer>below</layer>\n    <desktop>all</desktop>\n    <skip_taskbar>yes</skip_taskbar>\n    <skip_pager>yes</skip_pager>\n    <maximized>no</maximized>\n  </application>' \
    /etc/xdg/openbox/rc.xml
}

if [[ ${1:-} == --render-config ]]; then
  render_config
  exit
fi

# Load the image's normal X11 behavior with a browser menu for this stack.
# Keep the generated configuration outside the persistent profile volume.
config_dir=$(mktemp -d /tmp/camofox-openbox.XXXXXX)
export XDG_CONFIG_HOME="$config_dir"
mkdir "$config_dir/openbox"
config="$config_dir/openbox/rc.xml"
menu="$config_dir/openbox/menu.xml"
trap 'rm -f -- "$config" "$menu"; rmdir -- "$config_dir/openbox" "$config_dir"' EXIT
cp /opt/camofox-desktop/menu.xml "$menu"
render_config > "$config"
# Use our launcher in place of the image's default terminal autostart.
xsetroot -solid '#202832'
dbus-launch --exit-with-session /usr/bin/openbox --config-file "$config" \
  --startup '/bin/bash /opt/camofox-desktop/desktop-launcher.sh'
