# -*- coding: utf-8 -*-

# Was adapted from JamendoConfigureDialog.py
#
# Copyright (C) 2007 - Guillaume Desmottes
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import gobject
import gtk
import gconf, gnome

class LCDProcPluginConfigureDialog (object):
    gconf_keys = { 'scrolling' : '/apps/rhythmbox/plugins/lcdproc-plugin/scrolling'
             }
    scrolling_list = ['Bouncing', 'Rolling']
    def __init__(self, builder_file):
        self.gconf = gconf.client_get_default()

        builder = gtk.Builder()
        builder.add_from_file(builder_file)

        self.dialog = builder.get_object('config_dialog')
        self.scrolling_combobox = builder.get_object("scrolling_combobox")

        scrolling_text = self.gconf.get_string(LCDProcPluginConfigureDialog.gconf_keys['scrolling'])
        if not scrolling_text:
            scrolling_text = "Rolling"
        try:
            scrolling = LCDProcPluginConfigureDialog.scrolling_list.index(scrolling_text)
        except ValueError:
            scrolling = 0
        self.scrolling_combobox.set_active(scrolling)

        self.dialog.connect("response", self.dialog_response)
        self.scrolling_combobox.connect("changed", self.scrolling_combobox_changed)

    def get_dialog (self):
        return self.dialog

    def dialog_response (self, dialog, response):
        dialog.hide()

    def scrolling_combobox_changed (self, combobox):
        scrolling = self.scrolling_combobox.get_active()
        self.gconf.set_string(LCDProcPluginConfigureDialog.gconf_keys['scrolling'], LCDProcPluginConfigureDialog.scrolling_list[scrolling])
        #__init__.LCDProcPlugin.scrolling.set_scrollmode(scrolling)
