#!/usr/bin/python
# -*- coding: utf-8 -*-


import glob
import os
import re

from threading import Thread
from time import sleep
from subprocess import call


class AbstractCallback(object):
    u"""Absctract class for line callback.

        Registred callback will be invked for every new line. If your action depends on more than one line, you have to
        maintain state yourself.
    """

    def __init__(self):
        u"""Constructor. For now it's empty, but invoke this constructor for future compatibility."""

        pass

    def process_line(self, line, file_name):
        u"""Function that will be called for every line"""

        raise NotImplementedError

    def blink_screen(self):
        call("open -a BlinkScreen", shell=True)

    def say(self, message):
        say = "".join(["say '", message, "'"])
        call(say, shell=True)

    def notification(self, title, info):
        notification = "".join(["osascript -e 'display notification \"", info, "\" with title \"", title, "\"'"])
        call(notification, shell=True)

    def play_sound(self, sound):
        play = "".join(["afplay ", sound])
        call(play, shell=True)


class SimpleFindLineAbstractCalback(AbstractCallback):

    def __init__(self):
        super(SimpleFindLineAbstractCalback, self).__init__()

    def process_line(self, line, file_name):
        needed_text = self.get_needed_text().lower()
        if needed_text in line.lower():
            print self.text_reaction()

            def async_message():
                self.async_reaction()

            Thread(target = async_message).start()

    def get_needed_text(self):
        raise NotImplementedError

    def text_reaction(self):
        raise NotImplementedError

    def async_reaction(self):
        raise NotImplementedError


class LogWatch(object):
    u"""Class for watching files. Can watch multiple files at once."""

    def __init__(self, callbacks, path_pattern="./*.log", last_chars=0, refresh_delay=5):
        u"""Constructor.

        Callbacks - list of subclases of AbstractCallback.
        path_pattern - unix style path pattenr.
        last_chars - how many previous chars should be printed. If File is shorter, then will start form begining.
        refresh_delay - ms between each refresh
        """

        self.callbacks = callbacks
        self.path_pattern = path_pattern
        self.last_chars = last_chars

        self.watched_files = dict()

        while True: # main loop
            self.update_watched_files()
            self.tail_for_files()
            sleep(refresh_delay)


    def update_watched_files(self):
        u"""Function finds all files matching self.path_pattern.

        If function detect any changes (new files or file name points to different phisical file), updates configuration.
        """

        # Get files from unix style path regexp
        files = glob.glob(self.path_pattern)

        # Remove removed files
        for key in list(self.watched_files):
            if key not in files:
                 del self.watched_files[key]

        # Generate file ids. Some rotating logs mechanisms maintains constant name for current file.
        # We have to check if file name points to the same file, or to new one.
        files_stat = [(file_name, os.stat(file_name)) for file_name in files]
        files_ids = [(file_name, self.file_id(stat)) for file_name, stat in files_stat]

        # Add new files or reset configuration if known file name points to new file.
        for file_name, fid in files_ids:
            if self.watched_files.has_key(file_name):
                watched = self.watched_files[file_name]
                if fid != watched['fid']:
                    self.watched_files[file_name] = self.create_file_record(file_name, fid)
            else:
                self.watched_files[file_name] = self.create_file_record(file_name, fid)

    @staticmethod
    def file_id(file_name):
        u"""Function generate phisical file indentification.

        For rotating log files, sometime current log file has constant name, so every n-hours new file is created for
        know name. File identificator helps detecting such changes.
        """

        if os.name == 'posix':
            return "%x-%x" % (file_name.st_dev, file_name.st_ino)
        else:
            return "%f" % file_name.st_ctime

    @staticmethod
    def create_file_record(file_name, fid):
        u"""File record for storing informactions about known files."""

        return {
            'name': file_name,
            'fid': fid,
            'new': True,
            'last_pos': 0,
        }

    def tail_for_files(self):
        u"""Method iterate over files, checking if there is something new."""

        for file in self.watched_files.values(): # For every file
            print '-----------------------------'
            print file['name']
            print
            print

            with open(file['name'], 'r') as f:
                # Set possition, from which to start.
                # If new file go to end - self.last_chars. If file is shorter than self.last_chars then start from begining.
                # In case of known file, start form last possition.
                if file['new']:
                    try:
                        f.seek(0 - self.last_chars, 2) # move to end of file - last_chars
                    except:
                        f.seek(0) # If file is shorter then move to begining
                else:
                    f.seek(file['last_pos'], 0) # move to last readed possition

                # Iterate every new line of current file
                while True:
                    line = f.readline()
                    if line == '':
                        break
                    self.process_line(line, file)

                # Update state
                file['new'] = False
                file['last_pos'] = f.tell()

    def process_line(self, line, file):
        u"""Call all callbacks for current line"""
        for calback in self.callbacks:
            calback.process_line(line, file['name'])


class PrintLineCallback(AbstractCallback):
    u"""Just print every line. Sample callback, but usefull"""

    def __init__(self):
        super(PrintLineCallback, self).__init__()

    def process_line(self, line, file_name):
        print line.rstrip()


class ServerStartUpCallback(AbstractCallback):
    u"""Inform when Tomcat server is up and running."""

    terminal_message = "Server started in {}"
    sound = "~/Library/Sounds/sfx_00001.aiff"
    started_in = "You can work. It started in {}"

    def __init__(self):
        super(ServerStartUpCallback, self).__init__()
        self.startup_pattern = re.compile('INFO: Server startup in (\d+) ms')

    def process_line(self, line, file_name):
        found = self.startup_pattern.search(line.strip())
        if found is not None:
            time_ms = found.group(1)
            formated_time = self.format_time(time_ms)

            print ServerStartUpCallback.terminal_message.format(formated_time)

            # Executing all commands grouped in this function, takes some time.
            # To omit application locking, run it in new thread.
            def async_message():
                self.notification("Platform is UP", ServerStartUpCallback.started_in.format(formated_time))
                self.blink_screen()
                self.play_sound(ServerStartUpCallback.sound)

            Thread(target = async_message).start()

    def format_time(self, time):
        u"""Format mili seconds to hours, minutes, seconds and miliseconds.

        Use only values that are larger than 0 or any previous value was greater than 0"
        """
        time = int(time)

        mili_seconds = time % 1000
        time = time // 1000

        seconds = time % 60
        time = time // 60

        minutes = time % 60
        time = time // 60

        hours = time

        result = ""
        previous_appended = False

        if hours > 0 or previous_appended:
            result = "".join([result, " ", str(hours), "h"])
            previous_appended = True

        if minutes > 0 or previous_appended:
            result = "".join([result, " ", str(minutes), "m"])
            previous_appended = True

        if seconds > 0 or previous_appended:
            result = "".join([result, " ", str(seconds), "s"])
            previous_appended = True

        if mili_seconds > 0 or previous_appended:
            result = "".join([result, " ", str(mili_seconds), "ms"])
            previous_appended = True

        if not previous_appended:
            result = "".join([result, " 0ms"])

        return result


class ShutDownCallback(SimpleFindLineAbstractCalback):

    def __init__(self):
        super(ShutDownCallback, self).__init__()

    def get_needed_text(self):
        return "<-- Wrapper Stopped"

    def text_reaction(self):
        return "Server is DONW!"

    def async_reaction(self):
        self.notification("Platform is DOWN!", "Platform is DOWN!")
        self.blink_screen()
        self.say("Server is down!")


class RestartingCallback(SimpleFindLineAbstractCalback):

    def __init__(self):
        super(RestartingCallback, self).__init__()

    def get_needed_text(self):
        return "JVM requested a restart."

    def text_reaction(self):
        return "Restarting Requested"

    def async_reaction(self):
        self.notification("Restarting Requested!", "Restarting Requested!")
        self.say("Restarting requested!")


if __name__ == '__main__':

    callback_list = [
        PrintLineCallback(),
        ServerStartUpCallback(),
        ShutDownCallback(),
        RestartingCallback(),
    ]

    try :
        LogWatch(callback_list, "log/tomcat/console-*.log")
    except KeyboardInterrupt: # Without catching KeyboardInterrupt, ctrl+c results with ugly stack trace.
        print ""
        print ""
        print "BYE!"
        print ""
