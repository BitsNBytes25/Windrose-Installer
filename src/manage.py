#!/usr/bin/env python3
import os

# To allow running as a standalone script without installing the package, include the venv path for imports.
# This will set the include path for this path to .venv to allow packages installed therein to be utilized.
#
# IMPORTANT - any imports that are needed for the script to run must be after this,
# otherwise the imports will fail when running as a standalone script.
# import:org_python/venv_path_include.py

import logging

# Import the appropriate type of handler for the game installer.
# Common options are:
#from warlock_manager.apps.base_app import BaseApp
from warlock_manager.apps.steam_app import SteamApp

# Import the appropriate type of handler for the game services.
# Common options are:
from warlock_manager.services.base_service import BaseService
# from warlock_manager.services.rcon_service import RCONService
# from warlock_manager.services.socket_service import SocketService
# from warlock_manager.services.http_service import HTTPService

# Import the various configuration handlers used by this game.
# Common options are:
# from warlock_manager.config.cli_config import CLIConfig
from warlock_manager.config.ini_config import INIConfig
# from warlock_manager.config.json_config import JSONConfig
from warlock_manager.config.properties_config import PropertiesConfig
# from warlock_manager.config.unreal_config import UnrealConfig

# Load the application runner responsible for interfacing with CLI arguments
# and providing default functionality for running the manager.
from warlock_manager.libs.app_runner import app_runner

# If your script manages the firewall, (recommended), import the Firewall library
from warlock_manager.libs.firewall import Firewall

# Utilities provided by Warlock that are common to many applications
from warlock_manager.libs import utils

# Useful in some games
# from warlock_manager.formatters.cli_formatter import cli_formatter

# Select the baseline for mod support
# from warlock_manager.mods.base_mod import BaseMod
from warlock_manager.mods.warlock_nexus_mod import WarlockNexusMod


class GameMod(WarlockNexusMod):
	pass


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
			'manager': INIConfig('manager', os.path.join(utils.get_app_directory(), '.settings.ini'))
		}
		self.load()

	def first_run(self) -> bool:
		"""
		Perform any first-run configuration needed for this game

		:return:
		"""
		if os.geteuid() != 0:
			logging.error('Please run this script with sudo to perform first-run configuration.')
			return False

		super().first_run()

		# Create necessary directories if applicable
		# utils.makedirs(os.path.join(utils.get_app_directory(), 'Configs'))
		# utils.makedirs(os.path.join(utils.get_app_directory(), 'Packages'))

		# Install the game with Steam.
		# It's a good idea to ensure the game is installed on first run.
		# self.update()

		# First run is a great time to auto-create some services for this game too
		#services = self.get_services()
		#if len(services) == 0:
		#	# No services detected, create one.
		#	logging.info('No services detected, creating one...')
		#	self.create_service('valheim-server')
		#else:
		# Ensure services match new format
		#for service in services:
		#	logging.info('Ensuring %s service file is on latest format' % service.service)
		#	service.build_systemd_config()
		#	service.reload()

		return True

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
			'server': PropertiesConfig('server', os.path.join(self.get_app_directory(), 'server.properties'))
			# A common configuration tactic is to store binary parameters in a service file in Configs.
			# 'service': INIConfig('service', os.path.join(utils.get_base_directory(), 'Configs', 'service.%s.ini' % self.service))
		}
		self.load()

	def get_executable(self) -> str:
		"""
		Get the full executable for this game service
		:return:
		"""
		path = os.path.join(self.get_app_directory(), 'Game-Executable.bin')

		# Add arguments for the service, if applicable
		#args = cli_formatter(self.configs['service'], 'flag')
		#if args:
		#	path += ' ' + args

		return path

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
		if option == 'Server Port':
			# Update firewall for game port change
			if previous_value:
				Firewall.remove(int(previous_value), 'tcp')
			Firewall.allow(int(new_value), 'tcp', '%s game port' % self.game.name)
			success = True
		elif option == 'Query Port':
			# Update firewall for game port change
			if previous_value:
				Firewall.remove(int(previous_value), 'udp')
			Firewall.allow(int(new_value), 'udp', '%s query port' % self.game.name)
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
		# Return a string to a config parameter to allow changing, or a number to use a fixed port
		return [
			('Server Port', 'udp', '%s game port' % self.game.name, False)
		]

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
