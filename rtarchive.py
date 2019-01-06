#! /usr/bin/python

from bs4 import BeautifulSoup, Tag
import requests
import os
import urlparse
import string
import logging
import re
import threading

from requests.sessions import InvalidSchema
from requests.models import MissingSchema

VERSION = "0.1"
"""
    CHANGELOG
    0.1 - Initial working code and documentation
"""


HEADERS = {
    'User-Agent': 'RT Site Scraper'
}

valid_chars = "-_.%s%s" % (string.ascii_letters, string.digits)


"""
    TODO List:
        Add option to download all images from thread/journal to local storage
            - Make sure to handle broken links here
        Add links between files for replies
"""


class LimitReached(Exception):
    """
        Exception raised when a function reaches the max number of
        elements to parse
    """
    pass


class Archiver(threading.Thread):
    """
        Base class for objects performing archive functions on the
        RT site

        Args:
            maximum(:class:`int`): Maximum number of elements to scrape;
                None for no limit
            size(:class:`int`): Number of elements to put in one file
                where applicable
            path(:class:`str`): Path to the base directory where output
                will be located
            verbose(:class:`boolean`): Log debug to console
    """

    def __init__(self, maximum, size, path, verbose, thread_cb, progress_label):
        self.maximum = maximum if maximum else None
        self.size = size
        self.path = path
        self.logger_init(logging.DEBUG if verbose else logging.WARN)
        self.stoprequest = threading.Event()
        self.thread_cb = thread_cb
        self.progress_label = progress_label
        threading.Thread.__init__(self)
        self.logger.debug("Version: %s", VERSION)

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Archiver,self).join(timeout)

    def cleanup(self):
        if self.thread_cb:
            try:
                self.thread_cb()
            except RuntimeError:
                self.logger.warn("Window closed while scraping active")

    def write_update(self, update):
        if self.progress_label:
            try:
                self.progress_label.set(update)
            except RuntimeError:
                pass

    def get_version(self):
        """
            Returns the archiver version

            Returns:
                :class:`str` Version string of code
        """
        return VERSION

    def logger_init(self, level):
        """
            Initializes a logger to write to the console and a file

            Args:
                level(:class:`int`): Log level for the console
        """
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler()
        file_handler = logging.FileHandler("archive.log", mode="w")
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        file_handler.setLevel(logging.DEBUG)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def get_mods(self, post):
        """
            Gets the number of mods from a post

            Args:
                post(:class:`BeautifulSoup`): Post to get mod count from

            Returns:
                :class:`int` Number of mods
        """
        mods = post.find("p", class_="overall-mod")
        num = int(mods.attrs["data-value"])
        return num

    def get_page(self, url):
        """
            Downloads and parses a URL

            Args:
                url(:class:`str`): URL to download

            Returns:
                :class:`BeautifulSoup` Parsed page at URL

            Raises:
                :class:`IOError`: The page returned a bad status
        """
        self.logger.debug("Getting page at %s", url)
        page = requests.get(url, headers=HEADERS)
        if page.status_code != 200:
            self.logger.error("Failed to get page %s (%d)", url,
                              page.status_code)
            raise IOError
        return BeautifulSoup(page.content, 'html.parser')

    def download_image(self, url, path):
        """
            Downloads an image at a given URL

            Args:
                url(:class:`str`): URL of image to download
                path(:class:`str`): Path to store download at

            Raises:
                :class:`IOError`: The image returned a bad status
        """
        filename = os.path.split(urlparse.urlparse(url).path)[-1]
        filename = os.path.join(path, filename)
        if os.path.exists(filename):
            self.logger.debug("File exists, skipping %s", filename)
            return

        self.logger.debug("Downloading image at %s to %s", url, filename)
        r = requests.get(url, stream=True, headers=HEADERS)
        if r.status_code != 200:
            self.logger.error("Failed to get image %s (%d)", url,
                              r.status_code)
            raise IOError

        with open(filename, "wb") as f:
            for chunk in r:
                f.write(chunk)

    def check_path(self, path):
        """
            Checks a path and creates it if it doesn't exist.
            Equivilant to `mkdir -p`

            Args:
                path(:class:`str`): Path to create
        """
        if not os.path.exists(path):
            tokens = os.path.split(path)
            path_base = ""
            for token in tokens:
                if not token:
                    continue
                path_base = os.path.join(path_base, token)
                if not os.path.exists(path_base):
                    os.mkdir(path_base)

    def write_posts(self, posts, filename, path):
        """
            Writes a string of posts to an html file

            Args:
                posts(:class:`str`): String to write to file
                filename(:class:`str`): Name of file to write
                path(:class:`str`): Path to write file to
        """
        write_loc = os.path.join(path, filename + ".html")
        self.logger.debug("Writing posts to %s", write_loc)
        with open(write_loc, "wb") as f:
            f.write("<body>")
            f.write(posts)
            f.write("</body>")


class UserArchiver(Archiver):
    """
        Class that handles archiving user based content, such
        as images and journals

        Args:
            maximum(:class:`int`): Maximum number of elements to scrape;
                None for no limit
            size(:class:`int`): Number of elements to put in one file
                where applicable
            path(:class:`str`): Path to the base directory where output
                will be located
            verbose(:class:`boolean`): Log debug to console
            username(:class:`str`): Username to scrape
    """


    def __init__(self, maximum, size, path, verbose, username, thread_cb,
                 progress_label):
        self.username = username
        self.news_url = "https://roosterteeth.com/user/" + username
        self.img_url = self.news_url + "/images"
        super(ForumArchiver, self).__init__(maximum, size, path, verbose,
                                            thread_cb, progress_label)

    def verify_username(self):
        """
            Verifies existance of the username associated with this object

            Returns:
                :class:`boolean` True if user exists, false otherwise

            Raises:
                :class:`IOError` An unknown network error occured
        """
        r = requests.get(self.news_url, headers=HEADERS)
        if r.status_code == 200:
            self.logger.debug("User %s exists", self.username)
            return True
        if r.status_code == 404:
            self.logger.debug("User %s does not exist", self.username)
        else:
            self.logger.error("Unknown status code verifying user %s (%d)",
                              self.username, r.status_code)
            raise IOError
        return False

    def get_journal_title(self, soup):
        """
            Gets the title of a journal

            Args:
                soup(:class:`BeautifulSoup`): Journal to get the title of

            Returns:
                :class:`str` Title of the journal
        """
        title = soup.find("h3", class_="feed-item-title")
        if not title:
            return "default"
        title = soup.find("a")
        if not title:
            return "default"
        return title.decode_contents()

    def format_journal(self, element):
        """
            Prepares a journal to be written to a file

            Args:
                element(:class:`BeautifulSoup`): Post to be formatted

            Returns:
                :class:`str` Formatted string to write to file
        """
        mods = self.get_mods(element)
        title = self.get_journal_title(element)
        body = element.find("div", class_="post-content").decode_contents()
        body = body.encode('ascii', 'ignore')
        post_soup = BeautifulSoup("", "html.parser")

        header_tag = post_soup.new_tag("h3")
        header_tag.string = title
        post_soup.append(header_tag)

        post_soup.append(BeautifulSoup(body, "html.parser"))

        mod_tag = post_soup.new_tag("p")
        mod_tag.append(post_soup.new_tag("em"))
        mod_tag.em.string = "Mods: %d" % mods
        post_soup.append(mod_tag)

        post_soup.append(post_soup.new_tag("hr"))

        return post_soup.prettify()

    def write_journals(self, journals):
        """
            Writes all journals in a list to files

            Args(:class:`list`): List of formatted html strings to write
        """
        page_num = 1
        if self.path:
            base_path = os.path.join(self.path, "journals")
        else:
            base_path = os.path.join(self.username, "journals")
        self.check_path(base_path)

        while (page_num - 1) * self.size < len(journals):
            if page_num * self.size > len(journals):
                pages = journals[(page_num - 1) * self.size:]
            else:
                pages = journals[(page_num - 1) * self.size:
                                 page_num * self.size]

            self.logger.debug("Writing %d pages at page %d", len(pages),
                              page_num)

            page = "\n".join(pages)
            self.write_posts(page, str(page_num), base_path)
            page_num += 1

    def get_journals(self):
        """
            Finds and writes all journals specified by the class
        """
        journal_base_url = self.news_url + "?page="
        hashes = set()
        journals = []
        num_journals = 0
        page_num = 1
        try:
            while True:
                activity = self.get_page(journal_base_url + str(page_num))
                page_num += 1
                elements = activity.findAll("div", class_="media-content")
                if not elements:
                    break
                for element in elements:
                    """ Only save news posts """
                    post_tag = element.find("p", class_="post-tag-label")
                    if not post_tag or post_tag.text != "News":
                        continue
                    body = element.find("div", class_="post-content")
                    body = body.decode_contents()
                    hashes.add(hash(body))
                    """ Avoid duplicate journals """
                    if len(hashes) == num_journals:
                        self.logger.debug("Found duplicate hash")
                        continue
                    num_journals += 1
                    journals.append(self.format_journal(element))
                    if self.maximum is not None and \
                            num_journals >= self.maximum:
                        raise LimitReached

        except LimitReached:
            pass

        self.logger.debug("Preparing to write %d journals", len(journals))
        self.write_journals(journals)

    def get_image_links(self, url):
        """
            Finds all the image links at a given URL. Stops if all
            links on page are found, or it reaches a specified max

            Args:
                url(:class:`str`): URL to check for image links

            Returns:
                :class:`list` List of URLs of images to download

            Raises:
                :class:`IOError` Error returned on request
        """
        links = []
        soup = self.get_page(url)
        blks = soup.find_all("ul", class_='large-image-blocks')
        for blk in blks:
            for tag in blk.find_all("a"):
                link = tag.attrs['href']
                if link.rfind("album") != -1:
                    break
                imgpg = requests.get(str(link), headers=HEADERS)
                if imgpg.status_code != 200:
                    self.logger.error("Could not access %s (%d)", str(link),
                                      imgpg.status_code)
                    raise IOError
                im_soup = BeautifulSoup(imgpg.content, 'html.parser')
                im = im_soup.find("img", class_="full-image")
                links.append("http:" + im.attrs["src"])
                if self.maximum is not None:
                    self.maximum -= 1
                    if self.maximum <= 0:
                        return links

        return links

    def download_images(self, link, path):
        """
            Downloads all images on pages with a base of a given link

            Args:
                link(:class:`str`): URL of the base location to start
                    scraping images from
                path(:class:`str`): Base path to store images at

            Raises:
                :class:`LimitReached`: Reached maximum specified images
                    to be downloaded
        """
        page_num = 1
        self.check_path(path)

        self.logger.debug("Downloading images at %s", self.img_url)
        base_url = link + "?page="
        while True:
            links = self.get_image_links(base_url + str(page_num))
            if not links:
                break

            page_num += 1
            for link in links:
                self.download_image(link, path)

            if self.maximum is not None and self.maximum <= 0:
                raise LimitReached

    def get_images(self):
        """
            Download all images excluding albums
        """
        if self.path:
            path = os.path.join(self.path, "images")
        else:
            path = os.path.join(self.username, "images")

        self.download_images(self.img_url, path)

    def get_albums(self):
        """
            Download all images in albums
        """
        soup = self.get_page(self.img_url)
        blks = soup.find_all("ul", class_='large-image-blocks')
        if self.path:
            base_path = os.path.join(self.path, "images")
        else:
            base_path = os.path.join(self.username, "images")

        for blk in blks:
            for tag in blk.find_all("a"):
                link = tag.attrs["href"]
                if link.rfind("album") == -1:
                    break
                name_tag = tag.find("p", class_="name")
                album_name = name_tag.decode_contents()
                album_name = ''.join(c for c in str(album_name)
                                     if c in valid_chars)
                path = os.path.join(base_path, album_name)
                self.download_images(link, path)


class ForumArchiver(Archiver):
    """
        Class that handles archiving forum threads

        Args:
            maximum(:class:`int`): Maximum number of pages to scrape;
                None for no limit
            size(:class:`int`): Number of pages to put in one file
                where applicable
            path(:class:`str`): Path to the base directory where output
                will be located
            verbose(:class:`boolean`): Log debug to console
            url(:class:`str`): URL of forum to scrape
    """

    def __init__(self, maximum, size, path, verbose, url, thread_cb,
                 progress_label):
        self.url = url
        super(ForumArchiver, self).__init__(maximum, size, path, verbose,
                                            thread_cb, progress_label)

    def verify_forum(self):
        """
            Verifies existance of the forum associated with this object

            Returns:
                :class:`boolean` True if thread exists, false otherwise

            Raises:
                :class:`IOError` An unknown network error occured
        """
        try:
            r = requests.get(self.url, headers=HEADERS)
        except (InvalidSchema, MissingSchema):
            self.logger.error("Malformed URL %s", self.url)
            return False

        if r.status_code == 200:
            self.logger.debug("Thread at %s exists", self.url)
            return True
        if r.status_code == 404:
            self.logger.debug("Thread %s does not exist", self.url)
        else:
            self.logger.error("Unknown status code verifying thread %s (%d)",
                              self.url, r.status_code)
            raise IOError
        return False

    def format_replies(self, body):
        """
            Finds replies in text and modifies them to link to
            scraped posts

            Args:
                body(:class:`BeautifulSoup`): Post to have replies updated
        """
        def criterion(tag):
            return tag.has_attr('href') and re.search('In reply to', tag.text)

        replies = body.findAll(criterion)
        for reply in replies:
            reply.attrs["href"] = "#" + str(reply.attrs["href"].split("/")[-1])

    def get_body(self, post):
        """
            Gets the content of a post

            Args:
                post(:class:`BeautifulSoup`): Post to get content from

            Returns:
                :class:`str` Content of the post
        """
        body = post.find("div", class_="post-body")
        self.format_replies(body)
        return body.decode_contents().encode('ascii', 'ignore')

    def get_timestamp(self, post):
        """
            Gets the time and date a post was created

            Args:
                post(:class:`BeautifulSoup`): Post to get timestamp from

            Returns:
                :class:`str` Timestamp of post
        """
        stamp = post.find("p", class_="post-stamp")
        out = stamp.attrs["title"]
        return out

    def get_poster(self, post):
        """
            Gets the username of the post originator

            Args:
                post(:class:`BeautifulSoup`): Post to get poster from

            Returns:
                :class:`str` Username of poster
        """
        user = post.find("a")
        out = user.decode_contents()
        return out

    def get_post_num(self, post):
        """
            Gets the numeric identifier of the post

            Args:
                post(:class:`BeautifulSoup`): Post to get number from

            Returns:
                :class:`str` Post number with leading #
        """
        return post.findAll("a")[1].decode_contents()

    def get_posts(self, soup):
        """
            Gets all post elements from a page

            Args:
                soup(:class:`BeautifulSoup`): Page to get posts from

            Returns:
                :class:`list` List of BeautifulSoup objects containing
                    posts from page
        """
        return soup.findAll("div", class_="media-content")

    def get_forum_title(self, soup):
        """
            Gets the title of a forum thread

            Args:
                soup(:class:`BeautifulSoup`): Page to get title from

            Returns:
                :class:`str` Title of thread
        """
        title = soup.find("h1", class_="content-title")
        if self.thread_cb:
            try:
                self.thread_cb()
            except RuntimeError:
                self.logger.warn("Window closed while scraping active")
        if(title):
            title_text = title.decode_contents().strip()
            return ''.join(c for c in title_text if c in valid_chars)

        return "default"

    def get_page_count(self, soup):
        """
            Gets the page count of a thread

            Args:
                soup(:class:`BeautifulSoup`): Page to get page count

            Returns:
                :class:`int` Page count of a thread
        """
        pagination = soup.find("section", class_="pagination")
        if not pagination:
            return 1
        elements = pagination.findAll("li", class_="")
        if not elements:
            return 1
        href = elements[-1].find("a")
        if not href:
            return 1
        return int(href.decode_contents())

    def parse_page(self, soup):
        """
            Finds all posts in a page and formats them into a string

            Args:
                soup(:class:`BeautifulSoup`): Page to scrape

            Returns:
                :class:`str` String containing all posts from thread
                    formatted to be written to a file
        """
        posts = self.get_posts(soup)
        out = ""
        for post in posts:
            out += self.format_post(post)
        return out

    def format_post(self, post):
        """
            Formats a post for writting to a file. Extracts the poster,
            number of mods, post number, timestamp, and post content and
            arranges them for archive writing

            Args:
                post(:class:`BeautifulSoup`): Post to format

            Returns:
                :class:`str` Formatted post
        """
        poster = self.get_poster(post)
        mods = self.get_mods(post)
        post_num = self.get_post_num(post)
        timestamp = self.get_timestamp(post)
        body = self.get_body(post)
        post_soup = BeautifulSoup("", "html.parser")

        header_tag = post_soup.new_tag("h3")
        # Have to create it this way beacuse of the name attribute
        header_anchor = Tag(builder=post_soup.builder, name="a",
                            attrs={'name': post_num[1:]})

        header_anchor.string = poster
        header_tag.append(header_anchor)
        post_soup.append(header_tag)

        post_link_tag = post_soup.new_tag("a", href=post_num)
        info_tag = post_soup.new_tag("p")
        info_tag.append(post_link_tag)
        info_tag.a.string = post_num
        info_tag.append(" - %s" % timestamp)
        post_soup.append(info_tag)

        post_soup.append(BeautifulSoup(body, "html.parser"))

        mod_tag = post_soup.new_tag("p")
        mod_tag.append(post_soup.new_tag("em"))
        mod_tag.em.string = "Mods: %d" % mods
        post_soup.append(mod_tag)

        post_soup.append(post_soup.new_tag("hr"))

        return post_soup.prettify()

    def parse_thread(self):
        """
            Scrapes, formats, and writes to file the associated thread
        """
        base_url = urlparse.urlparse(self.url)
        if not all([base_url.scheme, base_url.netloc, base_url.path]):
            return 1
        base_url = base_url.scheme + "://" + base_url.netloc + base_url.path
        page = self.get_page(base_url)
        num_pages = self.get_page_count(page)
        self.check_path(self.path)

        out = ""
        if self.maximum is not None:
            num_pages = min(self.maximum, num_pages)
        for ii in range(1, num_pages+1):
            url = base_url + "?page=" + str(ii)
            self.write_update("Scraping page %d of %d" % (ii, num_pages))
            page = self.get_page(url)
            out += self.parse_page(page)
            if self.size and ii % self.size == 0:
                self.write_posts(out, str(ii/self.size), self.path)
                out = ""
            if self.stoprequest.isSet():
                self.logger.debug("Halting due to join request")
                break
        if out:
            self.write_posts(out, str(1 + (ii/self.size)), self.path)
            self.write_update("Wrote %d pages to %d files" %
                              (ii, (1+(ii/self.size))))
        else:
            self.write_update("Wrote %d pages to %d files" %
                              (ii, (ii/self.size)))
        self.cleanup()

    def run(self):
        self.parse_thread()
