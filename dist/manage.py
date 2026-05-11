#!/usr/bin/env python3
import os
import shutil
import socket
import sys
# Include the virtual environment site-packages in sys.path
here = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(here, '.venv')):
	print('Python environment not setup')
	exit(1)
sys.path.insert(
	0,
	os.path.join(
		here,
		'.venv',
		'lib',
		'python' + '.'.join(sys.version.split('.')[:2]), 'site-packages'
	)
)
from warlock_manager.apps.steam_app import SteamApp
from warlock_manager.services.base_service import BaseService
from warlock_manager.config.ini_config import INIConfig
from warlock_manager.config.json_config import JSONConfig
from warlock_manager.config.properties_config import PropertiesConfig
from warlock_manager.libs.app_runner import app_runner
from warlock_manager.libs.firewall import Firewall
from warlock_manager.libs import utils
from warlock_manager.libs.proton import get_proton_paths
from warlock_manager.libs.logger import logger
from warlock_manager.libs.get_wan_ip import get_wan_ip
from warlock_manager.mods.warlock_nexus_mod import WarlockNexusMod
# To allow running as a standalone script without installing the package, include the venv path for imports.
# This will set the include path for this path to .venv to allow packages installed therein to be utilized.
#
# IMPORTANT - any imports that are needed for the script to run must be after this,
# otherwise the imports will fail when running as a standalone script.

# Import the appropriate type of handler for the game installer.
# Common options are:
#from warlock_manager.apps.base_app import BaseApp

# Import the appropriate type of handler for the game services.
# Common options are:
# from warlock_manager.services.rcon_service import RCONService
# from warlock_manager.services.socket_service import SocketService
# from warlock_manager.services.http_service import HTTPService

# Import the various configuration handlers used by this game.
# Common options are:
# from warlock_manager.config.cli_config import CLIConfig
# from warlock_manager.config.unreal_config import UnrealConfig

# Load the application runner responsible for interfacing with CLI arguments
# and providing default functionality for running the manager.

# If your script manages the firewall, (recommended), import the Firewall library

# Utilities provided by Warlock that are common to many applications

# Useful in some games
# from warlock_manager.formatters.cli_formatter import cli_formatter

# Select the baseline for mod support
# from warlock_manager.mods.base_mod import BaseMod


class GameMod(WarlockNexusMod):
	pass


def get_local_ip():
	"""
	Connects to a known external address (like Google's DNS server)
	and retrieves the local IP address associated with that connection.
	This is generally more reliable than just using socket.gethostbyname(socket.gethostname()).
	"""
	try:
		# Create a socket object
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Connect the socket to a server (doesn't actually send data, just establishes the route)
		# We use Google's public DNS server address here as an example.
		sock.connect(("8.8.8.8", 80))

		# Once connected, we ask the socket for its local IP address
		local_ip = sock.getsockname()[0]
		return local_ip
	except Exception as e:
		print(f"An error occurred while fetching the IP address: {e}")
		return None
	finally:
		# Always close the socket when done! Good housekeeping!
		sock.close()


# For Steam games, swap 'BaseApp' with 'SteamApp'
class GameApp(SteamApp):
	"""
	Game application manager
	"""

	def __init__(self):
		super().__init__()

		self.name = 'Windrose'
		self.desc = 'Windrose Dedicated Server'
		# For steam games, include the steam ID
		self.steam_id = '4129620'
		self.service_handler = GameService
		# Set this to the class that handles the game mod system, if applicable
		self.mod_handler = GameMod
		self.service_prefix = 'windrose-'

		# Use this to mark certain features as disabled in this game manager
		# self.disabled_features = {'api'}

		self.configs = {
			'manager': INIConfig('manager', os.path.join(utils.get_base_directory(), '.settings.ini'))
		}
		self.load()

	def first_run(self) -> bool:
		"""
		Perform any first-run configuration needed for this game

		:return:
		"""
		if os.geteuid() != 0:
			logger.error('Please run this script with sudo to perform first-run configuration.')
			return False

		# Create necessary directories if applicable
		utils.makedirs(os.path.join(utils.get_base_directory(), 'Configs'))
		utils.makedirs(os.path.join(utils.get_base_directory(), 'Packages'))

		# Install the game with Steam.
		# It's a good idea to ensure the game is installed on first run.
		if not self.update():
			logger.error('Failed to update Steam')
			return False

		# Run migrations for the application
		self.run_migrations()

		# First run is a great time to auto-create some services for this game too
		services = self.get_services()
		if len(services) == 0:
			# No services detected, create one.
			logger.info('No services detected, creating one...')
			self.create_service('windrose-server')
		else:
			# Ensure services match new format
			for service in services:
				logger.info('Ensuring %s service file is on latest format' % service.service)
				service.build_systemd_config()
				service.reload()

		return True

	def get_option_options(self, option: str):
		"""
		Get the list of possible options for a configuration option
		:param option:
		:return:
		"""
		if option == 'Default Proton Path':
			return get_proton_paths()
		else:
			return super().get_option_options(option)

	def option_value_updated(self, option: str, previous_value, new_value) -> bool | None:
		"""
		Handle any special actions needed when an option value is updated

		:param option:
		:param previous_value:
		:param new_value:
		:return:
		"""
		if option == 'Default Proton Path':
			# Update the Proton path in the service config
			for svc in self.get_services():
				if svc.get_option_value('Proton Path') == previous_value:
					svc.set_option('Proton Path', new_value)
			return True

		return None

	def get_proton_path(self) -> str | None:
		"""
		Get the path to Proton as configured.
		:return:
		"""
		proton_path = self.get_option_value('Default Proton Path')
		if proton_path:
			return proton_path
		else:
			# It's not set yet!  Just return the first one found.
			paths = get_proton_paths()
			return paths[0] if len(paths) > 0 else None

	def remove(self):
		"""
		Remove this game and all instances under it

		:return:
		"""
		super().remove()

		#shutil.rmtree(os.path.join(utils.get_app_directory(), 'Configs'))
		#shutil.rmtree(os.path.join(utils.get_app_directory(), 'Packages'))


class GameService(BaseService):
	"""
	Service definition and handler
	"""
	def __init__(self, service: str, game: GameApp):
		"""
		Initialize and load the service definition
		:param file:
		"""
		super().__init__(service, game)
		self.configs = {
			'server': JSONConfig('game', os.path.join(utils.get_base_directory(), 'AppFiles', 'R5', 'ServerDescription.json')),
			'service': INIConfig('service', os.path.join(utils.get_base_directory(), 'Configs', 'service.%s.ini' % self.service))
		}
		self.load()

	def create_service(self):
		"""
		Create the systemd service for this game, including the service file and environment file
		:return:
		"""

		wan_ip = get_wan_ip()
		local_ip = get_local_ip()
		if wan_ip != local_ip:
			self.set_option('Use Direct Connection', False)
		else:
			self.set_option('Use Direct Connection', True)

		super().create_service()

		# New instances need the proton prefix
		self.set_option('Proton Path', self.game.get_proton_path())

		# Ensure the prefix exists for this instance.
		prefix_path = os.path.join(utils.get_base_directory(), 'prefixes', self.service)
		prefix_src = os.path.join(
			os.path.dirname(self.get_option_value('Proton Path')),
			'files/share/default_pfx'
		)
		if not os.path.exists(prefix_path):
			shutil.copytree(prefix_src, prefix_path)
			utils.ensure_file_ownership(prefix_path)

		self.build_systemd_config()
		self.reload()

	def get_environment(self) -> dict:
		"""
		Get the environment variables for this service as a dictionary

		:return:
		"""
		ret = {
			'XDG_RUNTIME_DIR': '/run/user/%s' % utils.get_app_uid(),
			'STEAM_COMPAT_CLIENT_INSTALL_PATH': os.path.join(utils.get_home_directory(), '.local/share/Steam'),
			'STEAM_COMPAT_DATA_PATH': os.path.join(utils.get_base_directory(), 'prefixes', self.service),
			'PROTON_USE_XALIA': 0,
			'DISPLAY': ':99'
		}

		return ret

	def get_executable(self) -> str:
		"""
		Get the full executable for this game service
		:return:
		"""

		proton_path = self.get_option_value('Proton Path')
		if not proton_path:
			# This needs something, so try to pull whatever path is available from the game manager.
			proton_path = self.game.get_proton_path()

		if not proton_path:
			logger.error('Unable to determine Proton path for %s' % self.service)
			return '/bin/false'

		binary = 'R5\Binaries\Win64\WindroseServer-Win64-Shipping.exe'
		options = ''
		flags = '-log'

		# Add arguments for the service, if applicable
		#args = cli_formatter(self.configs['service'], 'flag')
		#if args:
		#	path += ' ' + args

		return ' '.join([
			proton_path,
			'run',
			binary,
			options,
			flags
		])

	def get_option_options(self, option: str):
		"""
		Get the list of possible options for a configuration option
		:param option:
		:return:
		"""
		if option == 'Proton Path':
			return get_proton_paths()
		else:
			return super().get_option_options(option)

	def option_value_updated(self, option: str, previous_value, new_value) -> bool | None:
		"""
		Handle any special actions needed when an option value is updated
		:param option:
		:param previous_value:
		:param new_value:
		:return:
		"""
		success = None

		# Special option actions
		if option == 'Direct Connection Server Port':
			# Update firewall for game port change
			if previous_value:
				Firewall.remove(int(previous_value), 'tcp')
				Firewall.remove(int(previous_value), 'udp')
			Firewall.allow(int(new_value), 'tcp', '%s game port' % self.game.name)
			Firewall.allow(int(new_value), 'udp', '%s game port' % self.game.name)
			success = True

		# For games that need to regenerate systemd to apply changes
		#self.build_systemd_config()
		#self.reload()
		return success

	def is_api_enabled(self) -> bool:
		"""
		Check if API is enabled for this service
		:return:
		"""
		return (
			self.get_option_value('Enable RCON') and
			self.get_option_value('RCON Port') != '' and
			self.get_option_value('RCON Password') != ''
		)

	def get_api_port(self) -> int:
		"""
		Get the API port from the service configuration
		:return:
		"""
		return self.get_option_value('RCON Port')

	def get_api_password(self) -> str:
		"""
		Get the API password from the service configuration
		:return:
		"""
		return self.get_option_value('RCON Password')
	
	def get_players(self) -> list | None:
		"""
		Get a list of current players on the server, or None if the API is unavailable
		:return:
		"""
		return None

	def get_player_max(self) -> int:
		"""
		Get the maximum player count allowed on the server
		:return:
		"""
		return self.get_option_value('Max Players')

	def get_name(self) -> str:
		"""
		Get the name of this game server instance
		:return:
		"""
		return self.get_option_value('Level Name')

	def get_port(self) -> int | None:
		"""
		Get the primary port of the service, or None if not applicable
		:return:
		"""
		return self.get_option_value('Server Port')
	
	def get_port_definitions(self) -> list:
		"""
		Get a list of port definitions for this service

		Each entry in the returned list should contain 3 or 4 items:

		* Config name or integer of port (for non-definable ports)
		* 'UDP' or 'TCP' to indicate protocol
		* Short description of the port purpose
		* Optional boolean to indicate if this is an optional port (ie: not checked at startup)

		Example:

		```python
		return [
			('Game Port', 'UDP', 'Primary game port for clients to connect to', False),
			(25565, 'TCP', 'RCON port, statically assigned and cannot be changed', True)
		]
		```

		:return:
		"""

		if self.get_option('Use Direct Connection'):
			return [
				('Direct Connection Server Port', 'udp', '%s game port' % self.game.name, False),
				('Direct Connection Server Port', 'tcp', '%s game port' % self.game.name, False)
			]
		else:
			return []

	def get_game_pid(self) -> int:
		"""
		Get the primary game process PID of the actual game server, or 0 if not running
		:return:
		"""

		# For services that do not have a helper wrapper, it's the same as the process PID
		return self.get_pid()

		# For services that use a wrapper script, the actual game process will be different and needs looked up.
		'''
		# There's no quick way to get the game process PID from systemd,
		# so use ps to find the process based on the map name
		processes = subprocess.run([
			'ps', 'axh', '-o', 'pid,cmd'
		], stdout=subprocess.PIPE).stdout.decode().strip()
		exe = os.path.join(here, 'AppFiles/Vein/Binaries/Linux/VeinServer-Linux-')
		for line in processes.split('\n'):
			pid, cmd = line.strip().split(' ', 1)
			if cmd.startswith(exe):
				return int(line.strip().split(' ')[0])
		return 0
		'''

	def get_save_files(self) -> list | None:
		"""
		Get the list of supplemental files or directories for this game, or None if not applicable

		This list of files **should not** be fully resolved, and will use `self.get_save_directory()` as the base path.
		For example, to return `AppFiles/SaveData` and `AppFiles/Config`:

		```python
		return ['SaveData', 'Config']
		```

		:return:
		"""
		return None

	def get_enabled_mods(self) -> list[GameMod]:
		"""
		Get all enabled mods that are locally available on this service

		:return:
		"""
		# Do whatever logic is necessary for retrieving locally enabled mods for this service.
		return []

	def add_mod(self, mod: 'GameMod', force: bool = False) -> bool:
		"""
		Install a mod

		:param mod: Mod to install
		:param force: Force the installation even if the mod is already installed
		:return:
		"""
		# Do whatever logic is necessary for downloading and installing a mod.
		pass

	def remove_mod(self, mod: 'GameMod') -> bool:
		"""
		Remove a mod

		Will completely uninstall the requested mod

		:param mod:
		:return:
		"""
		pass


if __name__ == '__main__':
	app = app_runner(GameApp())
	app()
