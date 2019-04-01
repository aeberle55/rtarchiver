# rtarchiver
Archive threads, journals, and images from the legacy Roosterteeth site

Note that the [RT ToU](https://roosterteeth.com/terms-of-use) Section 14 disallows the scraping of the site. While this project does have the approval of RT Engineering, it is still offered for Educational Purposes Only.

## Executable Instructions

### Windows 10
To build, with PyInstaller run:
`PyInstaller --windowed --onefile -n rtarchiver archive_gui.py`
This will create an executable file with the name rtarchiver.exe

Run the executable like any other Windows application

### Linux
TODO

### Other OSs
Not Supported

## Script instructions
The raw python scripts can be run by anyone with Python2.7 installed on their computer. They require the package BeautifulSoup4, installation instructions for which can be found [here](https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-beautiful-soup). Also required is the requests library. Run the `archive_gui.py` script to use the GUI. You can also run `scrape_forum.py` to scrape a forum from the CLI or `scrape_user.py` for journals or images.
