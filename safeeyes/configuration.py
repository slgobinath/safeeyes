#!/usr/bin/env python
# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2017  Gobinath
# Copyright (C) 2026  Mel Dafert <m@dafert.at>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""This module contains the Config class and related logic around handling the
configuration file.
"""

import copy
import logging
from packaging.version import parse
import os
import shutil
import typing
from random import randint

from safeeyes import utility
from safeeyes.translations import translate as _

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib


class Config:
    """The configuration of Safe Eyes."""

    __user_config: dict[str, typing.Any]
    __system_config: dict[str, typing.Any]

    @classmethod
    def load(cls) -> "Config":
        # Read the config files
        user_config = utility.load_json(utility.CONFIG_FILE_PATH)
        user_config_disk = copy.deepcopy(user_config)
        system_config = utility.load_json(utility.SYSTEM_CONFIG_FILE_PATH)
        # If there any breaking changes in long_breaks, short_breaks or any other keys,
        # use the force_upgrade_keys list
        force_upgrade_keys: list[str] = []
        # force_upgrade_keys = ['long_breaks', 'short_breaks']

        if user_config is None:
            cls._initialize_config()
            user_config = copy.deepcopy(system_config)
            cfg = cls(user_config, system_config)
            cfg.save()

            # This gets called when the configuration file is not present, which
            # happens just after installation or manual deletion of
            # .config/safeeyes/safeeyes.json file. In this case, we want to force the
            # creation of a startup entry
            cls._enable_autostart_initial()
            return cfg
        else:
            system_config_version = system_config["meta"]["config_version"]
            meta_obj = user_config.get("meta", None)
            if meta_obj is None:
                # Corrupted user config
                user_config = copy.deepcopy(system_config)
            else:
                user_config_version = str(meta_obj.get("config_version", "0.0.0"))
                if parse(user_config_version) != parse(system_config_version):
                    # Update the user config
                    new_user_config = copy.deepcopy(system_config)
                    cls.__merge_dictionary(
                        user_config, new_user_config, force_upgrade_keys
                    )
                    user_config = new_user_config

        utility.merge_plugins(user_config)

        cfg = cls(user_config, system_config)

        if user_config != user_config_disk:
            cfg.save()

        # if _create_startup_entry finds a broken autostart symlink, it will repair
        # it
        # This intentionally only calls the non-flatpak method. In flatpak, there is no
        # way to know if the startup entry was deleted - so it would effectively request
        # it every time.
        # There should also be no broken symlink issues on flatpak.
        cls._create_startup_entry(force=False)

        return cfg

    def __init__(
        self,
        user_config: dict[str, typing.Any],
        system_config: dict[str, typing.Any],
    ):
        self.__user_config = user_config
        self.__system_config = system_config

    @classmethod
    def __merge_dictionary(cls, old_dict, new_dict, force_upgrade_keys: list[str]):
        """Merge the dictionaries."""
        for key in new_dict:
            if key == "meta" or key in force_upgrade_keys:
                continue
            if key in old_dict:
                new_value = new_dict[key]
                old_value = old_dict[key]
                if type(new_value) is type(old_value):
                    # Both properties have same type
                    if isinstance(new_value, dict):
                        cls.__merge_dictionary(old_value, new_value, force_upgrade_keys)
                    else:
                        new_dict[key] = old_value

    def clone(self) -> "Config":
        config = Config(
            user_config=copy.deepcopy(self.__user_config),
            system_config=self.__system_config,
        )
        return config

    def save(self) -> None:
        """Save the configuration to file."""
        logging.debug("Writing config to disk")
        utility.write_json(utility.CONFIG_FILE_PATH, self.__user_config)

    def get(self, key, default_value=None):
        """Get the value."""
        value = self.__user_config.get(key, default_value)
        if value is None:
            value = self.__system_config.get(key, None)
        return value

    def set(self, key, value):
        """Set the value."""
        self.__user_config[key] = value

    def __eq__(self, config):
        return self.__user_config == config.__user_config

    def __ne__(self, config):
        return self.__user_config != config.__user_config

    @classmethod
    def reset_config(cls) -> "Config":
        cls._initialize_config()

        # This calls _enable_autostart_initial()
        return Config.load()

    @classmethod
    def _initialize_config(cls) -> None:
        """Create the config file in XDG_CONFIG_HOME(or
        ~/.config)/safeeyes directory.
        """
        logging.info("Copy the config files to XDG_CONFIG_HOME(or ~/.config)/safeeyes")

        # Remove the ~/.config/safeeyes/safeeyes.json file
        utility.delete(utility.CONFIG_FILE_PATH)

        if not os.path.isdir(utility.CONFIG_DIRECTORY):
            utility.mkdir(utility.CONFIG_DIRECTORY)

        # Copy the safeeyes.json
        shutil.copy2(utility.SYSTEM_CONFIG_FILE_PATH, utility.CONFIG_FILE_PATH)

        # Add write permission (e.g. if original file was stored in /nix/store)
        os.chmod(utility.CONFIG_FILE_PATH, 0o600)

    @classmethod
    def request_autostart(cls) -> None:
        """User requested autostart be enabled."""
        logging.debug("autostart requested")
        if utility.is_flatpak():
            cls._request_autostart_portal(autostart=True)
        else:
            cls._create_startup_entry(force=True)

    @classmethod
    def disable_autostart(cls) -> None:
        """User requested autostart be disabled."""
        if utility.is_flatpak():
            cls._request_autostart_portal(autostart=False)
        else:
            cls._remove_startup_entry()

    @classmethod
    def _enable_autostart_initial(cls) -> None:
        """Config file was missing or reset - enable autostart by default."""
        if utility.is_flatpak():
            cls._request_autostart_portal(autostart=True)
        else:
            cls._create_startup_entry(force=True)

    @classmethod
    def _request_autostart_portal(cls, autostart: bool) -> None:
        """Request autostart for flatpak app."""
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        portal_proxy = Gio.DBusProxy.new_sync(
            connection=bus,
            flags=Gio.DBusProxyFlags.NONE,
            info=None,
            name="org.freedesktop.portal.Desktop",
            object_path="/org/freedesktop/portal/desktop",
            interface_name="org.freedesktop.portal.Background",
            cancellable=None,
        )

        token = 0 + randint(10000000, 90000000)
        if bus.props.unique_name is None:
            # not sure when this happens.
            # in any case - just set the expected_handle to something that it
            # shouldn't be so we hit the fallback path below
            sender = ""
            expected_handle = ""
        else:
            # see
            # https://github.com/flatpak/xdg-desktop-portal/blob/main/data/org.freedesktop.portal.Request.xml
            # for more information here
            sender = bus.props.unique_name.lstrip(":").replace(".", "_")

            expected_handle = (
                f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
            )

            bus.signal_subscribe(
                sender="org.freedesktop.portal.Desktop",
                interface_name="org.freedesktop.portal.Request",
                member="Response",
                object_path=expected_handle,
                arg0=None,
                flags=Gio.DBusSignalFlags.NONE,
                callback=cls.__receive_autostart,
                user_data={"autostart": autostart},
            )

        options = {
            "handle_token": GLib.Variant("s", f"{token}"),
            "reason": GLib.Variant("s", _("Safe Eyes wants to run in the background.")),
            "autostart": GLib.Variant("b", autostart),
            # not sure what this means...
            "dbus-activatable": GLib.Variant("b", False),
        }

        # Geary also just sends the app id here, so we presumably do not need a window
        parent_window = "io.github.slgobinath.SafeEyes"

        request_handle = portal_proxy.RequestBackground(  # type: ignore[attr-defined]
            "(sa{sv})", parent_window, options
        )

        if request_handle != expected_handle:
            # This is recommended as a fallback in
            # https://github.com/flatpak/xdg-desktop-portal/blob/main/data/org.freedesktop.portal.Request.xml
            # When this happens, there is a possibility of a race condition, in which
            # the reply can be missed
            logging.debug(
                f"expected handle {expected_handle}, got {request_handle}, falling back"
            )
            bus.signal_subscribe(
                sender="org.freedesktop.portal.Desktop",
                interface_name="org.freedesktop.portal.Request",
                member="Response",
                object_path=request_handle,
                arg0=None,
                flags=Gio.DBusSignalFlags.NONE,
                callback=cls.__receive_autostart,
                user_data={"autostart": autostart},
            )

    @classmethod
    def __receive_autostart(
        cls, conn, addr, object_path, interface_name, member, response, user_data
    ) -> None:
        """
        This method may or may not be called on older platforms due to the race
        condition above.
        If it does get called, and the request is denied, at least do some logging.
        """
        if response[0] != 0:
            logging.error("Autostart request was cancelled")
        else:
            results = response[1]

            if not results["background"]:
                logging.error("Running in the background was denied")

            if results["autostart"] != user_data["autostart"]:
                logging.error("Autostart was denied")

    @classmethod
    def _create_startup_entry(cls, force: bool = False) -> None:
        """Create start up entry for non-flatpak app."""
        startup_dir_path = os.path.join(utility.HOME_DIRECTORY, ".config/autostart")
        startup_entry = os.path.join(
            startup_dir_path, "io.github.slgobinath.SafeEyes.desktop"
        )

        create_link = False

        if force:
            # if force is True, just create the link
            create_link = True
        else:
            # if force is False, we want to avoid creating the startup symlink if it was
            # manually deleted by the user, we want to create it only if a broken one is
            # found
            if os.path.islink(startup_entry):
                # if the link exists, check if it is broken
                try:
                    os.stat(startup_entry)
                except FileNotFoundError:
                    # a FileNotFoundError will get thrown if the startup symlink is
                    # broken
                    create_link = True

        if create_link:
            logging.debug(f"Creating startup entry at {startup_entry}")
            # Create the folder if not exist
            utility.mkdir(startup_dir_path)

            # Remove existing files
            utility.delete(startup_entry)

            # Create the new startup entry
            try:
                os.symlink(utility.SYSTEM_DESKTOP_FILE, startup_entry)
            except OSError:
                logging.error("Failed to create startup entry at %s" % startup_entry)

        cls._cleanup_old_startup_entry()

    @classmethod
    def _remove_startup_entry(cls) -> None:
        """Remove start up entry."""
        startup_dir_path = os.path.join(utility.CONFIG_DIRECTORY, "autostart")
        startup_entry = os.path.join(
            startup_dir_path, "io.github.slgobinath.SafeEyes.desktop"
        )

        if os.path.exists(startup_entry):
            utility.delete(startup_entry)

        cls._cleanup_old_startup_entry()

    @classmethod
    def _cleanup_old_startup_entry(cls) -> None:
        startup_dir_path = os.path.join(utility.CONFIG_DIRECTORY, "autostart")

        # until Safe Eyes 2.1.5 the startup entry had another name
        # https://github.com/slgobinath/safeeyes/commit/684d16265a48794bb3fd670da67283fe4e2f591b#diff-0863348c2143a4928518a4d3661f150ba86d042bf5320b462ea2e960c36ed275L398
        obsolete_entry = os.path.join(startup_dir_path, "safeeyes.desktop")

        if os.path.exists(obsolete_entry):
            utility.delete(obsolete_entry)
