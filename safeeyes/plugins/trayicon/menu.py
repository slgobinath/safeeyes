# Safe Eyes is a utility to remind you to take break frequently
# to protect your eyes from eye strain.

# Copyright (C) 2025-26  Mel Dafert <m@dafert.at>
# Copyright (C) 2026 Archisman Panigrahi <apandada1@gmail.com>

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

import logging
import typing

from safeeyes import utility
from safeeyes.context import Context
from safeeyes.model import BreakType
from safeeyes.translations import translate as _


class TrayMenuCallbacks(typing.Protocol):
    def on_enable_clicked(self) -> None: ...

    def on_disable_clicked(self, time_to_wait: int) -> None: ...

    def on_manual_break_clicked(
        self, break_type: typing.Optional[BreakType]
    ) -> None: ...

    def show_settings(self) -> None: ...

    def show_about(self) -> None: ...

    def quit_safe_eyes(self) -> None: ...


def build_info_message(
    context: Context,
    *,
    active: bool,
    wakeup_time,
    next_break: typing.Optional[tuple[str, typing.Optional[str], bool]],
) -> str:
    breaks_found = context.api.has_breaks()
    info_message = _("No Breaks Available")

    if breaks_found:
        if active:
            if next_break is not None:
                (next_time, next_long_time, next_is_long) = next_break

                if next_long_time:
                    if next_is_long:
                        info_message = _("Next long break at %s") % (next_long_time)
                    else:
                        info_message = _("Next breaks at %(short)s/%(long)s") % {
                            "short": next_time,
                            "long": next_long_time,
                        }
                else:
                    info_message = _("Next break at %s") % (next_time)
        else:
            if wakeup_time:
                info_message = _("Disabled until %s") % utility.format_time(wakeup_time)
            else:
                info_message = _("Disabled until restart")

    return info_message


def build_menu_items(
    context: Context,
    plugin_config: dict,
    callbacks: TrayMenuCallbacks,
    *,
    active: bool,
    wakeup_time,
    menu_locked: bool,
    next_break: typing.Optional[tuple[str, typing.Optional[str], bool]],
) -> list[dict]:
    breaks_found = context.api.has_breaks()
    allow_disabling = plugin_config["allow_disabling"]

    disable_items = []

    if allow_disabling:
        disable_option_dynamic_id = 13

        for disable_option in plugin_config["disable_options"]:
            time_in_minutes = time_in_x = disable_option["time"]

            if not isinstance(time_in_minutes, int) or time_in_minutes <= 0:
                logging.error("Invalid time in disable option: " + str(time_in_minutes))
                continue
            time_unit = disable_option["unit"].lower()
            if time_unit == "seconds" or time_unit == "second":
                time_in_minutes = int(time_in_minutes / 60)
                label = context.locale.ngettext(
                    "For %(num)d Second", "For %(num)d Seconds", time_in_x
                ) % {"num": time_in_x}
            elif time_unit == "minutes" or time_unit == "minute":
                time_in_minutes = int(time_in_minutes * 1)
                label = context.locale.ngettext(
                    "For %(num)d Minute", "For %(num)d Minutes", time_in_x
                ) % {"num": time_in_x}
            elif time_unit == "hours" or time_unit == "hour":
                time_in_minutes = int(time_in_minutes * 60)
                label = context.locale.ngettext(
                    "For %(num)d Hour", "For %(num)d Hours", time_in_x
                ) % {"num": time_in_x}
            else:
                logging.error("Invalid unit in disable option: " + str(disable_option))
                continue

            ttw = time_in_minutes
            disable_items.append(
                {
                    "id": disable_option_dynamic_id,
                    "label": label,
                    "callback": lambda ttw=ttw: callbacks.on_disable_clicked(ttw),
                }
            )

            disable_option_dynamic_id += 1

        disable_items.append(
            {
                "id": 12,
                "label": _("Until restart"),
                "callback": lambda: callbacks.on_disable_clicked(-1),
            }
        )

    return [
        {
            "id": 1,
            "label": build_info_message(
                context,
                active=active,
                wakeup_time=wakeup_time,
                next_break=next_break,
            ),
            "icon-name": "io.github.slgobinath.SafeEyes-timer",
            "enabled": breaks_found and active,
        },
        {
            "id": 2,
            "type": "separator",
        },
        {
            "id": 3,
            "label": _("Enable Safe Eyes"),
            "enabled": breaks_found and not active,
            "callback": callbacks.on_enable_clicked,
            "hidden": not allow_disabling,
        },
        {
            "id": 4,
            "label": _("Disable Safe Eyes"),
            "enabled": breaks_found and active and not menu_locked,
            "children-display": "submenu",
            "children": disable_items,
            "hidden": not allow_disabling,
        },
        {
            "id": 5,
            "label": _("Take a break now"),
            "enabled": breaks_found and active and not menu_locked,
            "children-display": "submenu",
            "children": [
                {
                    "id": 9,
                    "label": _("Any break"),
                    "callback": lambda: callbacks.on_manual_break_clicked(None),
                },
                {
                    "id": 10,
                    "label": _("Short break"),
                    "callback": lambda: callbacks.on_manual_break_clicked(
                        BreakType.SHORT_BREAK
                    ),
                },
                {
                    "id": 11,
                    "label": _("Long break"),
                    "callback": lambda: callbacks.on_manual_break_clicked(
                        BreakType.LONG_BREAK
                    ),
                },
            ],
        },
        {
            "id": 6,
            "label": _("Settings"),
            "enabled": not menu_locked,
            "callback": callbacks.show_settings,
        },
        {
            "id": 7,
            "label": _("About"),
            "callback": callbacks.show_about,
        },
        {
            "id": 8,
            "label": _("Quit"),
            "enabled": not menu_locked,
            "callback": callbacks.quit_safe_eyes,
            "hidden": not allow_disabling,
        },
    ]
