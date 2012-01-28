# Copyright (c) 2010 Loic Andrieu <looustic at gmail.com>
# Copyright (c) 2011 Nikolai Knopp <mike_rofone at imail.de>
#
# This plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import rb
from gi.repository import GObject, Peas
from gi.repository import RB
#import gobject
#import gtk
import time
import gconf
from lcdproc_config_dialog import  LCDProcPluginConfigureDialog

from threading import Thread

from lcdproc.server import Server


##### BEGIN CONFIGURATION #####
#A display with 4 rows is assumed and this choice is not yet parameterised

#Number of characters per display row
DISPLAY_LENGTH=20

#String displayed to separate the start from the end in scrolling lines
SCROLL_ROLLING_SEPARATOR="  **  "

#How long to wait before scrolling a line (I don't know what unit that is in)
SCROLL_WAIT_TIME = 13

##### END CONFIGURATION   #####


#Field names for DB queries
STREAM_SONG_ARTIST = 'rb:stream-song-artist'
STREAM_SONG_TITLE  = 'rb:stream-song-title'
STREAM_SONG_ALBUM  = 'rb:stream-song-album'
NORMAL_SONG_ARTIST = 'artist'
NORMAL_SONG_TITLE  = 'title'
NORMAL_SONG_ALBUM  = 'album'

#Scrolling constants
SCROLL_BOUNCING="Bouncing"
SCROLL_ROLLING="Rolling"

#def extract_artist_and_title(stream_song_title):
#    details = stream_song_title.split('-')
#    if len(details) > 1:
#        artist = details[0].strip()
#        title = details[1].strip()
#    else:
#        details = stream_song_title.split('(')
#        if len(details) > 1:
#            title = details[0].strip()
#            artist = details[1].strip(') ')
#        else:
#            title = stream_song_title
#            artist = ""
#    return (artist, title)


class scroll_thread(Thread):
    def __init__(self, scrollmode):
        Thread.__init__(self)
        self.speed = 0.3
        self.running = True
        self.wait_time = SCROLL_WAIT_TIME
        self.scrollmode = scrollmode

    def set_scrollmode(self, scrollmode):
        self.scrollmode  = scrollmode
        for widget in self.widgets:
            self.reset_scrolling(widget)

    def reset_scrolling(self, widget):
        if self.scrollmode == SCROLL_ROLLING:
#            if self.text_exceeds_line(text):
#                # text longer than screen
#                widget_text = widget_text + "   **   "
            self.dir[widget] = self.wait_time
        else: # SCROLL_BOUNCING
            self.dir[widget] = -1
        self.offset[widget] = 0

    def center_offset(self, text):
        # if text is longer than display, the factor will be negative and thus it will return ""
        return " " * ((DISPLAY_LENGTH - text.__len__()) / 2)

    def text_exceeds_line(self, text):
        # if lengths are equal, text fits perfectly, so return false in that case
        return text.__len__() > DISPLAY_LENGTH

    def update_widget(self, widget, text):
        self.len[widget] = text.__len__()
        center_padding = self.center_offset(text);
        widget_text = center_padding + text
        self.reset_scrolling(widget)
        self.text[widget] = widget_text
        widget.set_text(self.text[widget])

    def config(self, widgets):
        self.widgets = widgets
        self.len = {}
        self.text = {}
        self.offset ={}
        self.dir = {}
        self.set_scrollmode(self.scrollmode)
        for widget in widgets:
            self.update_widget(widget, "");

    def run(self):
        try:
            while self.running:
                if self.scrollmode == SCROLL_BOUNCING:
                    for widget in self.widgets:
                        if self.len[widget] > DISPLAY_LENGTH:
                            if (self.dir[widget] < -1):
                                self.dir[widget]+=1
                            elif (self.dir[widget] > 1):
                                self.dir[widget]-=1
                            elif ((self.offset[widget] == (DISPLAY_LENGTH - self.len[widget])) and (self.dir[widget] == -1)) or ((self.offset[widget] == 0) and (self.dir[widget]== 1)):
                                self.dir[widget] = -self.dir[widget]*self.wait_time
                            else:
                                self.offset[widget] = self.offset[widget] + self.dir[widget]
                                scrolled_text = self.text[widget][-self.offset[widget]:DISPLAY_LENGTH-self.offset[widget]]
                                widget.set_text(scrolled_text[0:DISPLAY_LENGTH])
                else: #scrollmode == SCROLL_ROLLING
                    for widget in self.widgets:
                        if self.len[widget] > DISPLAY_LENGTH:
                            if (self.dir[widget] > 0):
                                self.dir[widget]-=1
                            elif self.offset[widget] == len(self.text[widget]) + len(SCROLL_ROLLING_SEPARATOR):
                                self.dir[widget] = self.wait_time
                                self.offset[widget] = 0
                            else:
                                self.offset[widget] = self.offset[widget] + 1;
                                text = self.text[widget] + SCROLL_ROLLING_SEPARATOR + self.text[widget]
                                scrolled_text = text[self.offset[widget]:DISPLAY_LENGTH+self.offset[widget]]
                                widget.set_text(scrolled_text[0:DISPLAY_LENGTH])
                
                time.sleep(self.speed)
        except:
            # connection to LCDd is broken
            print "in scrolling_thread: Connection to LCDd lost, deactivating plugin."
            self.stop_scrolling();

    def stop_scrolling(self):
        self.running = False

class LCDProcPlugin (GObject.Object, Peas.Activatable):
    __gtype_name__ = 'LCDProcPlugin'
    object = GObject.property(type=GObject.Object)

    def __init__ (self):
        GObject.Object.__init__ (self)
        self.scrolling = None
        self.running = False

    def time_callback(self, player, time):
        if not self.running and not self.connect():
            # no connection to LCDd
            print "Could not reconnect to LCDd"
            return
        
        try:
            if not (time >= 0 and player.get_playing()):
                return
            if self.streaming:
                # do not append remaining time or track
                self.scrolling.update_widget(self.time_widget, "Webradio" + ("%2d:%02d" % (time/60,  time % 60)).rjust(12," "))
            else:
                # append remaining time
                self.scrolling.update_widget(self.time_widget, self.track + (("%2d:%02d -" % (time/60,  time % 60)) + self.duration).rjust(13," "))
        except:
            # connection to LCDd is broken
            self.connectionlost("time_callback");

    def change_callback(self, player, entry):
        #print "change callback"
        if not self.running and not self.connect():
            # no connection to LCDd
            print "Could not reconnect to LCDd"
            return
        
#        try:
        if (entry == None):
            self.title = "No playback"
            self.album = ""
            self.artist = ""
            self.duration = ""
            self.track = ""
            self.streaming = False
        else:
            if entry.get_entry_type().props.category == RB.RhythmDBEntryCategory.STREAM:
                # streaming item - set station name as album and only update artist & title
                self.album = entry.get_string(RB.RhythmDBPropType.TITLE)
                self.artist = ""
                self.title = ""
                self.track = ""
                self.duration = ""
                self.streaming = True
            else:
                # regular item (local DB or LastFM)
                self.artist = entry.get_string(RB.RhythmDBPropType.ARTIST)
                self.album = entry.get_string(RB.RhythmDBPropType.ALBUM)
                self.title = entry.get_string(RB.RhythmDBPropType.TITLE)
                tracknumber = entry.get_ulong(RB.RhythmDBPropType.TRACK_NUMBER)
                if tracknumber > 0 and tracknumber < 100:
                    # valid track number
                    self.track = "Track" + str(tracknumber).rjust(2," ")
                else:
                    # invalid track number
                    self.track = ""
                seconds = entry.get_ulong(RB.RhythmDBPropType.DURATION)
                self.duration = "%2d:%02d" % (seconds/60,  seconds % 60)
                self.streaming = False
        
        self.update_widgets()
#        except:
#            # connection to LCDd is broken
#            self.connectionlost("change_callback");
    
    def update_widgets(self):
        self.scrolling.update_widget(self.title_widget, self.title)
        self.scrolling.update_widget(self.album_widget, self.album)
        self.scrolling.update_widget(self.artist_widget, self.artist)
        self.scrolling.update_widget(self.time_widget, self.duration)
        
    # copied from im-status plugin
    def playing_song_property_changed (self, sp, uri, property, old, new):
        if not self.running and not self.connect():
            # no connection to LCDd
            print "Could not reconnect to LCDd"
            return
        #print "prop callback: old %s new %s uri %s prop %s" % (old, new, uri, property)
#        if not self.streaming:
#            # do not update
#            return
        relevant = False
        if sp.get_playing () and property in (NORMAL_SONG_ARTIST,STREAM_SONG_ARTIST):
            self.artist = new
            relevant = True
        elif sp.get_playing () and property in (NORMAL_SONG_TITLE,STREAM_SONG_TITLE):
            if new.count(" - ") >= 1:
                # contains "Artist - Title"
                fields = new.split(" - ",1)
                self.artist = fields[0]
                self.title = fields[1]
            else:
                # only title
                self.title = new
            relevant = True
        elif sp.get_playing () and property in (NORMAL_SONG_ALBUM,STREAM_SONG_ALBUM):
            self.album = new
            relevant = True
        
        if relevant:
            self.update_widgets()

    def connectionlost(self, source):
        print "in " + source + ": Connection to LCDd lost, disconnecting plugin (will try to reconnect)"
        self.disconnect()
    
    def do_activate(self):
        self.shell = self.object
        if not self.connect():
             # LCDd not running
            print "LCDd not running, plugin not initialising"
            self.running = False
            self.inited = False
            return
        self.pec_id = self.shell.props.shell_player.connect('playing-song-changed', self.change_callback)
        self.pspc_id = self.shell.props.shell_player.connect ('playing-song-property-changed', self.playing_song_property_changed)
        self.inited = True
        print "Connected to LCDProc, loading plugin"


    def connect(self):
        try:
            self.lcd = Server()
        except:
            # LCDd not running
            self.running = False
            return False

        self.lcd.start_session()
        self.running = True
        
        self.screen1 = self.lcd.add_screen("Screen1")
        self.screen1.set_heartbeat("off")
        self.screen1.set_priority("foreground")
        
        self.counter = 0
        self.title_widget = self.screen1.add_string_widget("Widget1", x = 1, y = 1 , text = "")
        self.artist_widget = self.screen1.add_string_widget("Widget2", x = 1, y = 2 , text = "")
        self.album_widget = self.screen1.add_string_widget("Widget3", x = 1, y = 3 , text = "")
        self.time_widget = self.screen1.add_string_widget("Widget4", x = 1, y = 4 , text = "")
        scrollmode = gconf.client_get_default().get_string(LCDProcPluginConfigureDialog.gconf_keys['scrolling'])
        if not scrollmode:
            scrollmode = SCROLL_ROLLING
        self.scrolling = scroll_thread(scrollmode)
        self.scrolling.config([self.title_widget, self.album_widget, self.artist_widget, self.time_widget])
        self.scrolling.start()
        
        self.pec_idd = self.shell.props.shell_player.connect('elapsed-changed', self.time_callback)
        self.change_callback(self.shell.props.shell_player,self.shell.props.shell_player.get_playing_entry())
#        self.time_callback(self.shell.props.shell_player,-1)
        print "(Re-)Connected to LCDProc"
        return True

    def do_deactivate(self):
        self.disconnect()
        if self.inited:
            #plugin was running at some point
            self.shell.props.shell_player.disconnect(self.pec_id)
            del self.pec_id
            del self.pspc_id
        del self.shell
        print "Plugin unloaded"

    def disconnect(self):
        if not self.running:
            # LCDd was not running, nothing to clean up
            return
        
        self.running = False;
        self.scrolling.stop_scrolling()
        self.shell.props.shell_player.disconnect(self.pec_idd)
        del self.pec_idd
        del self.scrolling
        del self.title_widget
        del self.album_widget
        del self.artist_widget
        del self.time_widget
        del self.screen1
        self.lcd.tn.close()
        del self.lcd
        print "Plugin disconnected"
        
    #FIXME Does not work since API changes
    def create_configure_dialog(self, dialog=None):
        if not dialog:
            builder_file = self.find_file("config_dlg.glade")
            dialog = LCDProcPluginConfigureDialog(builder_file).get_dialog()
            dialog.present()
        return dialog


