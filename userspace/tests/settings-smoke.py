#!/usr/bin/python3
# Build-time smoke test: verify the libadwaita/GTK4 APIs the settings app uses.
import gi

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gtk

assert hasattr(Adw, 'AlertDialog')
assert hasattr(Adw.AlertDialog, 'set_extra_child')
assert hasattr(Adw, 'PreferencesWindow')
assert hasattr(Adw, 'PreferencesPage')
assert hasattr(Gtk, 'FileDialog')
print('GTK4/libadwaita API smoke test OK')
