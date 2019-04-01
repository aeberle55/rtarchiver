#! /usr/bin/python

import sys
import os
import tkinter as tk
import tkMessageBox
from tkinter import *
from tkinter import Frame, Tk, Button, BOTH, filedialog

from rtarchive import VERSION, ForumArchiver, JournalArchiver, ImageArchiver

DEBUG = False

class Window(Frame):
    """
        Class containing GUI frame

        Kwargs:
            master(:class:`Tk`): Tkinter object to use as root

        Attrs:
            ARCHIVE_TYPES(:class:`list`): Tupple mapping archive action to idx
    """

    ARCHIVE_TYPES = [
        ("Scrape Journals", 0),
        ("Scrape Images", 1),
        ("Scrape Forum", 2)
    ]

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master = master
        self.init_window()
        self.verbose = DEBUG
        self.active_thread = None

    def get_dir(self):
        """
            Opens a File Dialog to set the directory to store the archive
        """
        temp_path = filedialog.askdirectory()
        if not temp_path:
            return
        self.archive_path = temp_path
        self.dir_entry.config(state=tk.NORMAL)
        self.dir_entry.delete(0,tk.END)
        self.dir_entry.insert(0, self.archive_path)
        self.dir_entry.config(state="readonly")

    def set_archive_type(self):
        """
            Modifies the GUI based on the archive type selected by the user
        """
        if self.archive_type.get() < 0 or \
                self.archive_type.get() >= len(self.ARCHIVE_TYPES):
            return
        archive = self.archive_type.get()
        self.withdraw_all()
        if archive == 0:
            self.display_journal()
        elif archive == 1:
            self.display_images()
        else:
            self.display_forum()

    def scrape_cb(self):
        """
            Callback from the thread running the archiver on completion

            Note: This will terminate the application when the message is
            closed. Originaly it was only meant to reset for the next op,
            but an odd bug causes additional threads to be created each
            time a new one is started. Stopping the program ended up being
            the only fix I could find
        """
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.master.quit()

    def begin_scraping(self):
        """
            Gathers and validates the user information, then begins the
            archive process in a new thread
        """
        archive = self.archive_type.get()
        self.start_button.config(state=tk.DISABLED)

        self.active_thread = None
        self.progress_text = tk.StringVar("")
        self.progress_label = tk.Label(self, textvariable=self.progress_text,
                                       width=40, height=3, wraplength=350)

        if archive == 0:
            # Journal archive
            try:
                max_journals = int(self.user_max_entry.get())
            except ValueError:
                tkMessageBox.showerror("Error", "Max Journals must be numeric")
                self.start_button.config(state=tk.NORMAL)
                return
            try:
                journals_per_page = int(self.journal_pages_entry.get())
            except ValueError:
                tkMessageBox.showerror("Error", "Journals per page must be "
                                       "numeric")
                self.start_button.config(state=tk.NORMAL)
                return
            username = self.user_entry.get()
            self.active_thread = JournalArchiver(max_journals,
                                                 journals_per_page,
                                                 self.archive_path,
                                                 self.verbose,
                                                 username,
                                                 self.scrape_cb,
                                                 self.progress_text)
            if not self.active_thread.verify():
                tkMessageBox.showerror("Error", "Username not found")
                self.start_button.config(state=tk.NORMAL)
                return
        elif archive == 1:
            # Image archive
            try:
                max_images = int(self.user_max_entry.get())
            except ValueError:
                tkMessageBox.showerror("Error", "Max Images must be numeric")
                self.start_button.config(state=tk.NORMAL)
                return
            username = self.user_entry.get()
            self.active_thread = ImageArchiver(max_images,
                                               0,
                                               self.archive_path,
                                               self.verbose,
                                               username,
                                               self.scrape_cb,
                                               self.progress_text)
            if not self.active_thread.verify():
                tkMessageBox.showerror("Error", "Username not found")
                self.start_button.config(state=tk.NORMAL)
                return
        else:
            # Forum archive
            try:
                self.maximum_pages = int(self.forum_max_entry.get())
            except ValueError:
                tkMessageBox.showerror("Error", "Maximum Pages must be numeric")
                self.start_button.config(state=tk.NORMAL)
                return
            try:
                self.pages_per_file = int(self.forum_pages_entry.get())
            except ValueError:
                tkMessageBox.showerror("Error", "Entries per page must be numeric")
                self.start_button.config(state=tk.NORMAL)
                return
            self.forum_url = self.url_entry.get()
            self.active_thread = ForumArchiver(self.maximum_pages,
                                               self.pages_per_file,
                                               self.archive_path,
                                               self.verbose,
                                               self.forum_url,
                                               self.scrape_cb,
                                               self.progress_text)
            if not self.active_thread.verify():
                tkMessageBox.showerror("Error", "Forum URL not found")
                self.start_button.config(state=tk.NORMAL)
                return

        self.progress_label.grid(row=4, column=4, sticky=tk.W)
        self.active_thread.start()
        self.active_thread = self.active_thread
        self.stop_button.config(state=tk.NORMAL)
        self.start_button.config(state=tk.DISABLED)

    def stop_scraping(self):
        """
            Halts the scraping process
        """
        self.join(0.1)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def url_entered(self):
        """
            Activates the start button if a URL has been entered
        """
        self.start_button.config(state=tk.NORMAL)
        return True

    def username_entered(self):
        """
            Activates the start button if a username has been entered
        """
        self.start_button.config(state=tk.NORMAL)
        return True

    def init_directory(self):
        """
            Initializes the directory entry portion of the GUI
        """
        start_row = len(self.ARCHIVE_TYPES)
        self.archive_path = os.getcwd()
        self.dir_label = tk.Label(self, text="Current Directory:")
        self.dir_label.grid(row=start_row, column=0, sticky=tk.W, pady=10)
        self.dir_entry = tk.Entry(self, width=50)
        self.dir_entry.insert(0, self.archive_path)
        self.dir_entry.config(state="readonly")
        self.dir_entry.grid(row=start_row, column=1, sticky=tk.W, pady=10)

        self.path_button = Button(self, text="Directory", command=self.get_dir)
        self.path_button.grid(row=start_row+1, column=0, sticky=tk.W, pady=10)

    def init_archive_types(self):
        """
            Initializes the archive type entry portion of the GUI
        """
        self.archive_type = IntVar()
        self.archive_type.set(-1)
        for a_name, a_type in self.ARCHIVE_TYPES:
            tk.Radiobutton(self, text=a_name, padx=5,
                           variable=self.archive_type,
                           command=self.set_archive_type,
                           value=a_type).grid(row=a_type, column=0, sticky=tk.W,
                           pady=10)

    def init_forum(self):
        """
            Initializes the forum archive portion of the GUI
        """
        self.url_entry = tk.Entry(self, width=50, validate='key',
                                  vcmd=self.url_entered)
        self.url_label = tk.Label(self, text="Thread URL:")

        self.forum_max_entry = tk.Entry(self, width=5)
        self.forum_max_entry.insert(0, "0")
        self.forum_max_label = tk.Label(self,
                                        text="Max scraped pages (0=No Limit)")

        self.forum_pages_entry = tk.Entry(self, width=5, text="5")
        self.forum_pages_entry.insert(0, "25")
        self.forum_pages_label = tk.Label(self, text="Pages per file")

    def init_journal(self):
        """
            Initializes the journal archive portion of the GUI
        """
        self.user_max_label_text.set("Max Downloaded Journals (0=No Limit)")

        self.journal_pages_entry = tk.Entry(self, width=5, text="25")
        self.journal_pages_entry.insert(0, "25")
        self.journal_pages_label = tk.Label(self, text="Journals per file")

    def init_images(self):
        """
            Initializes the image archive portion of the GUI
        """
        self.user_max_label_text.set("Max Downloaded Images (0=No Limit)")

    def init_user(self):
        """
            Initializes the user specific portion of the GUI
        """
        self.user_entry = tk.Entry(self, width=20, validate='key',
                                   vcmd=self.username_entered)
        self.user_label = tk.Label(self, text="Username:")

        self.user_max_entry = tk.Entry(self, width=5)
        self.user_max_entry.insert(0, "0")
        self.user_max_label_text = tk.StringVar()
        self.user_max_label = tk.Label(self,
                                       textvariable=self.user_max_label_text)

        self.init_journal()
        self.init_images()

    def withdraw_forum(self):
        """
            Hides the forum archive specific portion of the GUI
        """
        self.url_entry.grid_forget()
        self.url_label.grid_forget()
        self.forum_max_entry.grid_forget()
        self.forum_max_label.grid_forget()
        self.forum_pages_entry.grid_forget()
        self.forum_pages_label.grid_forget()

    def withdraw_journal(self):
        """
            Hides the journal archive specific portion of the GUI
        """
        self.user_entry.grid_forget()
        self.user_label.grid_forget()
        self.user_max_entry.grid_forget()
        self.user_max_label.grid_forget()
        self.journal_pages_entry.grid_forget()
        self.journal_pages_label.grid_forget()

    def withdraw_images(self):
        """
            Hides the image archive specific portion of the GUI
        """
        self.user_entry.grid_forget()
        self.user_label.grid_forget()
        self.user_max_entry.grid_forget()
        self.user_max_label.grid_forget()

    def withdraw_all(self):
        """
            Hides all archive type specific elements from the GUI
        """
        self.withdraw_forum()
        self.withdraw_images()
        self.withdraw_journal()

    def display_forum(self):
        """
            Displays forum archive specific portions of the GUI
        """
        self.url_entry.grid(row=0, column=3, sticky=tk.W, pady=10)
        self.url_label.grid(row=0, column=2, sticky=tk.E, pady=10)
        self.forum_max_entry.grid(row=1, column=3, sticky=tk.W, pady=10)
        self.forum_max_label.grid(row=1, column=2, sticky=tk.E, pady=10)
        self.forum_pages_entry.grid(row=2, column=3, sticky=tk.W, pady=10)
        self.forum_pages_label.grid(row=2, column=2, sticky=tk.E, pady=10)

    def display_journal(self):
        """
            Displays journal archive specific portions of the GUI
        """
        self.user_max_label_text.set("Max Downloaded Journals (0=No Limit)")
        self.user_entry.grid(row=0, column=3, sticky=tk.W, pady=10)
        self.user_label.grid(row=0, column=2, sticky=tk.E)
        self.user_max_entry.grid(row=1, column=3, sticky=tk.W, pady=10)
        self.user_max_label.grid(row=1, column=2, sticky=tk.E, pady=10)
        self.journal_pages_entry.grid(row=2, column=3, sticky=tk.W, pady=10)
        self.journal_pages_label.grid(row=2, column=2, sticky=tk.E, pady=10)

    def display_images(self):
        """
            Displays image archive specific portions of the GUI
        """
        self.user_max_label_text.set("Max Downloaded Images (0=No Limit)")
        self.user_entry.grid(row=0, column=3, sticky=tk.W, pady=10)
        self.user_label.grid(row=0, column=2, sticky=tk.E)
        self.user_max_entry.grid(row=1, column=3, sticky=tk.W, pady=10)
        self.user_max_label.grid(row=1, column=2, sticky=tk.E, pady=10)

    def init_window(self):
        """
            Initializes the window and associated functions
        """
        self.master.title("RT Archiver v%s" % VERSION)
        self.pack(fill=BOTH, expand=1)
        self.init_archive_types()
        self.init_directory()
        self.init_user()
        self.init_forum()

        self.start_button = Button(self, text="Start", state=tk.DISABLED,
                                   command=self.begin_scraping)
        self.start_button.grid(row=5, column=5, sticky=tk.E, pady=10, padx=10)
        self.stop_button = Button(self, text="Stop", state=tk.DISABLED,
                                  command=self.stop_scraping)
        self.stop_button.grid(row=5, column=6, sticky=tk.E, pady=10, padx=5)


    def join(self, timeout=None):
        """
            Sends signal and blocks for up to timeout seconds waiting for
            archive thread to complete

            Kwargs:
                timeout(:class:`Numeric`): Max timeout to block waiting
        """
        if self.active_thread:
            self.active_thread.join(timeout)



def main():
    root = Tk()
    app = Window(root)
    root.forced_close = False
    def on_close():
        """
            Called when exiting by pressing X
        """
        root.forced_close = True
        root.destroy()
    root.protocol("WM_DELETE_WINDOW",  on_close)
    app.mainloop()
    app.join()
    if not root.forced_close:
        tkMessageBox.showinfo("Complete", "Action is complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
