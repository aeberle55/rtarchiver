#! /usr/bin/python

from bs4 import BeautifulSoup, Tag
import requests
import os
import urlparse
import string
import logging
import re

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
    pass


class Archiver(object):

    def logger_init(self, level):
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

    def __init__(self, maximum, size, path, verbose):
        self.maximum = maximum if maximum else None
        self.size = size
        self.path = path
        self.logger_init(logging.DEBUG if verbose else logging.WARN)

    def get_mods(self, post):
        mods = post.find("p", class_="overall-mod")
        num = int(mods.attrs["data-value"])
        return num

    def get_page(self, url):
        self.logger.debug("Getting page at %s", url)
        page = requests.get(url, headers=HEADERS)
        if page.status_code != 200:
            self.logger.error("Failed to get page %s (%d)", url,
                              page.status_code)
            raise IOError
        return BeautifulSoup(page.content, 'html.parser')

    def download_image(self, url, path):
        filename = os.path.split(urlparse.urlparse(url).path)[-1]
        filename = os.path.join(path, filename)
        if os.path.exists(filename):
            self.logger.debug("File exists, skipping %s", filename)
            return

        self.logger.debug("Downloading image at %s to %s", url, filename)
        r = requests.get(url, stream=True, headers=HEADERS)
        with open(filename, "wb") as f:
            for chunk in r:
                f.write(chunk)

    def check_path(self, path):
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
        write_loc = os.path.join(path, filename + ".html")
        self.logger.debug("Writing posts to %s", write_loc)
        with open(write_loc, "wb") as f:
            f.write("<body>")
            f.write(posts)
            f.write("</body>")


class UserArchiver(Archiver):

    def __init__(self, maximum, size, path, verbose, username):
        self.username = username
        self.news_url = "https://roosterteeth.com/user/" + username
        self.img_url = self.news_url + "/images"
        super(UserArchiver, self).__init__(maximum, size, path, verbose)

    def get_journal_title(self, soup):
        title = soup.find("h3", class_="feed-item-title")
        if not title:
            return "default"
        title = soup.find("a")
        if not title:
            return "default"
        return title.decode_contents()

    def format_journal(self, element):
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
        links = []
        soup = self.get_page(url)
        blks = soup.find_all("ul", class_='large-image-blocks')
        for blk in blks:
            for tag in blk.find_all("a"):
                link = tag.attrs['href']
                if link.rfind("album") != -1:
                    break
                imgpg = requests.get(str(link))
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

    def download_images(self, path):
        page_num = 1
        self.check_path(path)

        self.logger.debug("Downloading images at %s", self.img_url)
        base_url = self.img_url + "?page="
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
        if self.path:
            path = os.path.join(self.path, "images")
        else:
            path = os.path.join(self.username, "images")

        self.download_images(path)

    def get_albums(self):
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

    def __init__(self, maximum, size, path, verbose, url, filename):
        self.url = url
        self.filename = filename
        super(ForumArchiver, self).__init__(maximum, size, path, verbose)

    def format_replies(self, body):
        def criterion(tag):
            return tag.has_attr('href') and re.search('In reply to', tag.text)

        replies = body.findAll(criterion)
        for reply in replies:
            reply.attrs["href"] = "#" + str(reply.attrs["href"].split("/")[-1])

    def get_body(self, post):
        body = post.find("div", class_="post-body")
        self.format_replies(body)
        return body.decode_contents().encode('ascii', 'ignore')

    def get_timestamp(self, post):
        stamp = post.find("p", class_="post-stamp")
        out = stamp.attrs["title"]
        return out

    def get_poster(self, post):
        user = post.find("a")
        out = user.decode_contents()
        return out

    def get_post_num(self, post):
        return post.findAll("a")[1].decode_contents()

    def get_posts(self, soup):
        return soup.findAll("div", class_="media-content")

    def get_forum_title(self, soup):
        title = soup.find("h1", class_="content-title")
        if(title):
            title_text = title.decode_contents().strip()
            return ''.join(c for c in title_text if c in valid_chars)

        return "default"

    def get_last_page(self, soup):
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
        posts = self.get_posts(soup)
        out = ""
        for post in posts:
            out += self.format_post(post)
        return out

    def format_post(self, post):
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
        base_url = urlparse.urlparse(self.url)
        if not all([base_url.scheme, base_url.netloc, base_url.path]):
            return 1
        base_url = base_url.scheme + "://" + base_url.netloc + base_url.path
        page = self.get_page(base_url)
        num_pages = self.get_last_page(page)
        filename = self.filename
        if not filename:
            filename = self.get_forum_title(page)
        path = os.path.join(self.path, filename)
        if not os.path.exists(path):
            os.mkdir(path)

        out = ""
        for ii in range(1, num_pages+1):
            url = base_url + "?page=" + str(ii)
            page = self.get_page(url)
            out += self.parse_page(page)
            if self.size and ii % self.size == 0:
                self.write_posts(out, str(ii/self.size), path)
                out = ""
            if self.maximum is not None and ii >= self.maximum:
                break
        if out:
            self.write_posts(out, str(1 + (ii/self.size)), path)
