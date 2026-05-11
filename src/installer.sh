#!/bin/bash
#
# Install Game Server
#
# Please ensure to run this script as root (or at least with sudo)
#
# @LICENSE AGPLv3
# @AUTHOR  Charlie Powell <cdp1337@bitsnbytes.dev>
# @CATEGORY Game Server
# @TRMM-TIMEOUT 600
# @WARLOCK-TITLE Windrose
# @WARLOCK-IMAGE media/some-game-image.webp
# @WARLOCK-ICON media/some-game-icon.webp
# @WARLOCK-THUMBNAIL media/some-game-thumbnail.webp
#
# Supports:
#   Debian 12, 13
#   Ubuntu 24.04
#
# Requirements:
#   None
#
# TRMM Custom Fields:
#   None
#
# Syntax:
#   MODE_UNINSTALL=--uninstall - Perform an uninstallation
#   OVERRIDE_DIR=--dir=<src> - Use a custom installation directory instead of the default (optional)
#   SKIP_FIREWALL=--skip-firewall - Do not install or configure a system firewall
#   NONINTERACTIVE=--non-interactive - Run the installer in non-interactive mode (useful for scripted installs)
#   BRANCH=--branch=<str> - Use a specific branch of the management script repository DEFAULT=main
#   DEBUG=--debug - Include to show debug output
#
# Changelog:
#   20260318 - Update boilerplate script for v2 of the API
#   20251103 - New installer
#

############################################
## Parameter Configuration
############################################

# Version of this installation script, bump when you release new versions.
INSTALLER_VERSION="v20260510"

# Name of the game (used to create the directory)
GAME="Windrose"

GAME_DESC="Windrose Dedicated Server"

# If your repo URL is github.com/username/repo, then this should be "username/repo" without the "github.com" or "https://"
REPO="BitsNBytes25/Windrose-Installer"

WARLOCK_GUID="b5453ff4-e65e-3975-a9db-3ec4c12cb911"

# Set to the username to use for this game.
# Steam generally recommends using 'steam', but this can be whatever makes sense.
GAME_USER="steam"

# Game application directory to contain the management api and game files.
# For steam or other shared user games, it makes sense to have it as /home/user/game.
# For games what use their own user such as Minecraft, this should probably be /home/user or similar.
GAME_DIR="/home/${GAME_USER}/${GAME}"

# Set the minimum version of the Warlock Manager API to use for this project
# If a newer version of the branch version is available, that will be used instead,
# for example, "2.2.12" will use "2.2.54" if .54 is the latest, but NOT "2.3.13"
# https://github.com/BitsNBytes25/Warlock-Manager
MANAGER_VERSION="2.2.12"

# compile:usage
# compile:argparse
# scriptlet:_common/require_root.sh
# scriptlet:_common/get_firewall.sh
# scriptlet:_common/package_install.sh
# scriptlet:_common/download.sh
# scriptlet:_common/firewall_install.sh
# scriptlet:bz_eval_tui/prompt_text.sh
# scriptlet:bz_eval_tui/prompt_yn.sh
# scriptlet:bz_eval_tui/print_header.sh
# scriptlet:warlock/install_warlock_manager.sh
# scriptlet:bz_eval_log/log.sh

print_header "$GAME_DESC *unofficial* Installer ${INSTALLER_VERSION}"

############################################
## Installer Actions
############################################

##
# Install the game server
#
# Expects the following variables:
#   GAME_USER    - User account to install the game under
#   GAME_DIR     - Directory to install the game into
#   GAME_DESC    - Description of the game (for logging purposes)
#
function install_application() {
	print_header "Performing install_application"

	local debug
	debug=''
	if [ $DEBUG -eq 1 ]; then
		debug='--debug'
	fi

	# Create the game user account
	# This will create the account with no password, so if you need to log in with this user,
	# run `sudo passwd $GAME_USER` to set a password.
	if [ -z "$(getent passwd $GAME_USER)" ]; then
		log_info "Creating user account ${GAME_USER}"
		useradd -m -U $GAME_USER
	fi

	# Retrieve the home directory for the specified user
	USER_HOME=$(getent passwd "$GAME_USER" | cut -d: -f6)

	# Check if the retrieval was successful
	if [ -z "$USER_HOME" ]; then
		log_error "Could not find home directory for user '$GAME_USER'"
		exit 1
	fi

	# If the target home directory already exists, ensure it's owned by the actual user.
	# This is important in case the operator does something like 'mkdir /home/steam' as root
	# without realizing that would completely break permissions for that target.
	if [ -e "$USER_HOME" ]; then
		log_info "Ensuring correct ownership of ${USER_HOME}"
		chown $GAME_USER:$GAME_USER "$USER_HOME" -R
	fi

	# Ensure the target directory exists and is owned by the game user
	if [ ! -d "$GAME_DIR" ]; then
		log_info "Creating game directory ${GAME_DIR}"
		mkdir -p "$GAME_DIR"
		chown $GAME_USER:$GAME_USER "$GAME_DIR"
	fi

	# Preliminary requirements
	package_install curl sudo python3-venv

	# For java-based games, you can install specific versions of Java if necessary.
	# Include # scriptlet:openjdk/install.sh as a header include
	# and run install_openjdk 21 here.

	if [ "$FIREWALL" == "1" ]; then
		if [ "$(get_enabled_firewall)" == "none" ]; then
			# No firewall installed, go ahead and install the system default firewall
			firewall_install
		fi
	fi

	# Most games install into AppFiles, so ensure it's created.
	[ -e "$GAME_DIR/AppFiles" ] || sudo -u $GAME_USER mkdir -p "$GAME_DIR/AppFiles"
	#[ -e "$GAME_DIR/Configs" ] || sudo -u $GAME_USER mkdir -p "$GAME_DIR/Configs"
	#[ -e "$GAME_DIR/Packages" ] || sudo -u $GAME_USER mkdir -p "$GAME_DIR/Packages"


	# To download a game with steamcmd, include the following header
	#  # scriptlet:steam/install-steamcmd.sh
	# and use:
	#install_steamcmd
	## Run Steamcmd to ensure it's available; fixes the ERROR! Failed to install app '...' (Missing configuration) issue
	#if ! sudo -u $GAME_USER /usr/games/steamcmd +login anonymous +quit; then
	#	log_error "Steamcmd could not be ran!  Unable to install game"
	#	exit 1
	#fi
	
	# Install the management script
	if ! install_warlock_manager "$REPO" "$BRANCH" "$MANAGER_VERSION"; then
		log_error "Warlock Manager could not be installed!  Unable to install game"
		exit 1
	fi

	# If other PIP packages are required for your management interface,
	# add them here as necessary, for example:
	#  sudo -u $GAME_USER $GAME_DIR/.venv/bin/pip install name-of-package

	# If you need to forward parameters to the game manager from the installer,
	# call set-config with the appropriate key/value here.
	# sudo -u $GAME_USER $GAME_DIR/manage.py $debug set-config "Feature Name" "$FEATURE_VALUE"

	# Install installer (this script) for uninstallation or manual work
	download "https://raw.githubusercontent.com/${REPO}/refs/heads/${BRANCH}/dist/installer.sh" "$GAME_DIR/installer.sh"
	chmod +x "$GAME_DIR/installer.sh"
	chown $GAME_USER:$GAME_USER "$GAME_DIR/installer.sh"


	# Register this application install with Warlock so it can be picked up by the web manager.
	if [ -n "$WARLOCK_GUID" ]; then
		[ -d "/var/lib/warlock" ] || mkdir -p "/var/lib/warlock"
		echo -n "$GAME_DIR" > "/var/lib/warlock/${WARLOCK_GUID}.app"
	fi
}

##
# Upgrade logic for 1.0 to 2.2 to handle migration of ENV and overrides
#
function upgrade_application_1_0() {
	local LEGACY_SERVICE
	local SERVICE_PATH
	local debug

	LEGACY_SERVICE="some-name"
	SERVICE_PATH="/etc/systemd/system/${LEGACY_SERVICE}.service"
	debug=''
	if [ $DEBUG -eq 1 ]; then
		debug='--debug'
	fi

	# Migrate existing service to new format
	# This gets overwrote by the manager, but is needed to tell the system that the service is here.
	if [ -e "${SERVICE_PATH}" ] && [ ! -e "$GAME_DIR/Environments" ]; then
		sudo -u $GAME_USER mkdir -p "$GAME_DIR/Environments"
		sudo -u $GAME_USER mkdir -p "$GAME_DIR/Migrations"

		# Export this configuration so the new system can re-obtain all the configuration values
		# This is important because v1 to v2.2 changed CLI parameters.
		"$GAME_DIR/manage.py" $debug --service "$LEGACY_SERVICE" --get-configs > "$GAME_DIR/Migrations/${LEGACY_SERVICE}.configs-$(date +%Y%m%d%H%M%S).json"

		# Extract out current environment variables from the systemd file into their own dedicated file
		egrep '^Environment' "${SERVICE_PATH}" | sed 's:^Environment=::' > "$GAME_DIR/Environments/${LEGACY_SERVICE}.env"
		chown $GAME_USER:$GAME_USER "$GAME_DIR/Environments/${LEGACY_SERVICE}.env"
		# Trim out those envs now that they're not longer required
		cat "${SERVICE_PATH}" | egrep -v '^Environment=' > "${SERVICE_PATH}.new"
		mv "${SERVICE_PATH}.new" "${SERVICE_PATH}"

		if [ -e "${SERVICE_PATH}.d" ] && [ -e "${SERVICE_PATH}.d/override.conf" ]; then
			# If there is an override, (used in version 1.0),
			# grab the CLI and move it to a notes document so the operator can manually review it.
			touch "$GAME_DIR/Notes.txt"
			echo "    !! IMPORTANT - Service commands are now generated dynamically, " >> "$GAME_DIR/Notes.txt"
			echo "    so please manually migrate the following CLI options to your game." >> "$GAME_DIR/Notes.txt"
			echo "" >> "$GAME_DIR/Notes.txt"
			egrep '^ExecStart=' "${SERVICE_PATH}.d/override.conf" >> "$GAME_DIR/Notes.txt"
			chown $GAME_USER:$GAME_USER "$GAME_DIR/Notes.txt"
			rm -fr "${SERVICE_PATH}.d/override.conf"
			rm -fr "${SERVICE_PATH}.d"
		fi
	fi
}

##
# Perform any steps necessary for upgrading an existing installation.
#
function upgrade_application() {
	print_header "Existing installation detected, performing upgrade"

	# Uncomment if you need this
	# upgrade_application_1_0
}

##
# Perform any operations necessary after the dependency installation is complete.
#
# Generally this will use the management API to perform the actual installation.
#
function postinstall() {
	print_header "Performing postinstall"

	local debug
	debug=''
	if [ $DEBUG -eq 1 ]; then
		debug='--debug'
	fi

	# First run setup
	if ! $GAME_DIR/manage.py $debug first-run; then
		log_error "First run of game manager failed!"
		exit 1
	fi
}

##
# Uninstall the game server
#
# Expects the following variables:
#   GAME_DIR     - Directory where the game is installed
#   GAME_SERVICE - Service name used with Systemd
#
function uninstall_application() {
	print_header "Performing uninstall_application"

	local debug
	debug=''
	if [ $DEBUG -eq 1 ]; then
		debug='--debug'
	fi

	$GAME_DIR/manage.py $debug remove --confirm

	# Management scripts
	[ -e "$GAME_DIR/manage.py" ] && rm "$GAME_DIR/manage.py"
	[ -e "$GAME_DIR/configs.yaml" ] && rm "$GAME_DIR/configs.yaml"
	[ -d "$GAME_DIR/.venv" ] && rm -rf "$GAME_DIR/.venv"

	if [ -n "$WARLOCK_GUID" ]; then
		# unregister Warlock
		[ -e "/var/lib/warlock/${WARLOCK_GUID}.app" ] && rm "/var/lib/warlock/${WARLOCK_GUID}.app"
	fi
}

############################################
## Pre-exec Checks
############################################

if [ $DEBUG -eq 1 ]; then
	LOG_LEVEL=4  # Set logging to DEBUG
fi

if [ $MODE_UNINSTALL -eq 1 ]; then
	MODE="uninstall"
elif [ -e "$GAME_DIR/AppFiles" ]; then
	MODE="reinstall"
else
	# Default to install mode
	MODE="install"
fi


if [ -e "$GAME_DIR/Environments" ]; then
	# Check for existing service files to determine if the service is running.
	# This is important to prevent conflicts with the installer trying to modify files while the service is running.
	for envfile in "$GAME_DIR/Environments/"*.env; do
		SERVICE=$(basename "$envfile" .env)
		# If there are no services, this will just be '*.env'.
		if [ "$SERVICE" != "*" ]; then
			if systemctl -q is-active $SERVICE; then
				echo "$GAME_DESC service is currently running, please stop all instances before running this installer."
				echo "You can do this with: sudo systemctl stop $SERVICE"
				exit 1
			fi
		fi
	done
fi


if [ -n "$OVERRIDE_DIR" ]; then
	# User requested to change the install dir!
	# This changes the GAME_DIR from the default location to wherever the user requested.
	if [ -e "/var/lib/warlock/${WARLOCK_GUID}.app" ] ; then
		# Check for existing installation directory based on Warlock registration
		GAME_DIR="$(cat "/var/lib/warlock/${WARLOCK_GUID}.app")"
		if [ "$GAME_DIR" != "$OVERRIDE_DIR" ]; then
			echo "ERROR: $GAME_DESC already installed in $GAME_DIR, cannot override to $OVERRIDE_DIR" >&2
			echo "If you want to move the installation, please uninstall first and then re-install to the new location." >&2
			exit 1
		fi
	fi

	GAME_DIR="$OVERRIDE_DIR"
	echo "Using ${GAME_DIR} as the installation directory based on explicit argument"
elif [ -e "/var/lib/warlock/${WARLOCK_GUID}.app" ]; then
	# Check for existing installation directory based on service file
	GAME_DIR="$(cat "/var/lib/warlock/${WARLOCK_GUID}.app")"
	echo "Detected installation directory of ${GAME_DIR} based on service registration"
else
	echo "Using default installation directory of ${GAME_DIR}"
fi


############################################
## Installer
############################################


# Operations needed to be performed during a new installation
if [ "$MODE" == "install" ]; then

	if [ $SKIP_FIREWALL -eq 1 ]; then
		echo "Firewall explictly disabled, skipping installation of a system firewall"
		FIREWALL=0
	elif prompt_yn -q --default-yes "Install system firewall?"; then
		FIREWALL=1
	else
		FIREWALL=0
	fi

	install_application

	postinstall

	# Print some instructions and useful tips
    print_header "$GAME_DESC Installation Complete"
fi

# Operations needed to be performed during a reinstallation / upgrade
if [ "$MODE" == "reinstall" ]; then

	FIREWALL=0

	upgrade_application

	install_application

	postinstall

	# Print some instructions and useful tips
    print_header "$GAME_DESC Installation Complete"

	# If there are notes generated during installation, print them now.
    if [ -e "$GAME_DIR/Notes.txt" ]; then
    	cat "$GAME_DIR/Notes.txt"
	fi
fi

# Operations needed to be performed during an uninstallation
if [ "$MODE" == "uninstall" ]; then
	if [ $NONINTERACTIVE -eq 0 ]; then
		if prompt_yn -q --invert --default-no "This will remove all game binary content"; then
			exit 1
		fi
		if prompt_yn -q --invert --default-no "This will remove all player and map data"; then
			exit 1
		fi
	fi

	if prompt_yn -q --default-yes "Perform a backup before everything is wiped?"; then
		$GAME_DIR/manage.py backup
	fi

	uninstall_application
fi
