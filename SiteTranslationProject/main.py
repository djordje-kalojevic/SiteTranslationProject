"""Utility used primarily in site translation,
or the scraping of whole web sites."""

from os import system
from os.path import split, splitext, isfile
from tkinter import Tk
from tkinter.simpledialog import askstring
from tkinter.messagebox import showinfo, showerror, askyesno
from tkinter.filedialog import askopenfilename, asksaveasfilename
import sys
from time import perf_counter, sleep
from random import uniform
from warnings import catch_warnings, filterwarnings
from pandas import DataFrame, read_xml
import chromedriver_autoinstaller as driver_installer
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (NoSuchElementException,
                                        StaleElementReferenceException)
from selenium.webdriver.remote.webdriver import WebDriver
from alive_progress import alive_bar
from PIL import Image


def create_program_mainloop(transparent_icon_location: str) -> Tk:
    """Creates an instance of tk.Tk and replaces its icon with a transparent one."""

    if not isfile(transparent_icon_location):
        transparent_icon = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        transparent_icon.save(transparent_icon_location, "ICO")

    root = Tk()
    root.title("")
    # hides its window
    root.withdraw()
    # 'True' applies this icon to all other windows
    root.iconbitmap(True, transparent_icon_location)

    return root


def custom_chrome_options(headless=True) -> Options:
    """Creates custom Chrome options object.\n
    By default chrome driver is in the headless mode
    so that it uses far fewer resources but this can be turned off
    via the 'headless' parameter."""

    driver_installer.install()
    new_options = Options()
    new_options.add_argument("--incognito")

    # suppresses driver's output
    new_options.add_argument("log-level=3")
    new_options.add_experimental_option("excludeSwitches", ["enable-logging"])

    # grants access to more sites
    new_options.add_argument("--allow-running-insecure-content")
    new_options.add_argument("--ignore-certificate-errors")

    if headless:
        new_options.add_argument("--headless")

    return new_options


def find_suitable_file(root: Tk) -> tuple[list[str], list[str], str]:
    """Prompts user to select a file containing links,
    and checks if the file contains suitable links."""
    suitable_file_found = False
    while not suitable_file_found:
        link_list, file_dir = process_file(root)

        processed_link_list, discarded_links = link_preprocessing(link_list)

        number_links = len(processed_link_list)

        if number_links == 0:
            answer = askyesno(
                title="No suitable links were found!",
                message=("Please check the selected file and verify "
                         "that it has links suitable for extraction.\n"
                         "Would you like to select a different file?"))
            if not answer:
                sys.exit()
        else:
            suitable_file_found = True

    return processed_link_list, discarded_links, file_dir


def process_file(root: Tk) -> tuple[list[str], str]:
    """Reads selected file and returns its contents."""
    valid_file_found = False
    while not valid_file_found:
        file = askopenfilename(parent=root,
                               title="Choose a file containing links",
                               filetypes=[("XML file", "*.xml"),
                                          ("Text file", "*.txt")])

        if not file:
            sys.exit()

        file_dir = split(file)[0]
        file_extension = splitext(file)[1]

        if file_extension == ".xml":
            df = read_xml(file)

            if not "loc" in df.columns:
                showerror(
                    title="Invalid XML file",
                    message=(
                        "Please insert an .xml file from www.xml-sitemaps.com "
                        "or simply a .txt file and try again."))
            else:
                df = df["loc"]
                link_list = df.tolist()
                valid_file_found = True

        if file_extension == ".txt":
            with open(file, "r", encoding="utf-8") as txt_file:
                links = txt_file.read().splitlines()
                link_list = list(links)
                valid_file_found = True

    return link_list, file_dir


def link_preprocessing(link_list: list[str]) -> tuple[list[str], list[str]]:
    """Goes over links and makes them compatible with textise.net.
    Additionally, removes all invalid links and stores them to a .txt file."""
    discarded_links = []
    processed_link_list = []

    for link in link_list:
        link = link.lower()
        slash_removed = False

        if link.endswith("/"):
            processed_link = link[:-1]
            slash_removed = True

        # formats links so that Textise can use them
        if link.startswith("https://"):
            processed_link = link[6:]
        elif link.startswith("http://"):
            processed_link = link[5:]
        elif link.startswith("www."):
            processed_link = "//" + link[4:]
        else:
            discarded_links.append(link)
            continue

        # removes incompatible links
        if link.endswith((".pdf", "rss=1", "atom=1")):
            discarded_links.append(link)
            continue

        # restores the slash as it can break some links
        if slash_removed:
            processed_link += "/"

        processed_link_list.append(processed_link)

    return processed_link_list, discarded_links


def check_xpath(driver: WebDriver, link: str) -> bool:
    """Checks whether the inputted Xpath is the correct one.
    Requires users confirmation."""
    check_performed = False
    xpath = askstring(title="Please insert the xpath", prompt="Xpath?:")

    while not check_performed:
        scraped_text = []

        # iterating over links, and loading them on www.textise.net
        new_link = "https://www.textise.net/showText.aspx?strURL=https%253A" + link
        driver.get(new_link)
        original_link = "https:" + link

        timer_start = perf_counter()

        link_scraped = False
        link_skipped = False

        while not link_scraped and not link_skipped:
            try:
                timer_end = perf_counter()
                time_elapsed = timer_end - timer_start

                # check if the link is invalid or inaccessible in some other way
                if time_elapsed > 15:
                    link_skipped = True

                page_source = driver.find_element(by=By.XPATH, value=xpath)
                page_source = page_source.text
                text = page_source.split("\n")
                scraped_text.append(original_link)
                scraped_text.extend(text)

                # if link extraction was successful it goes to another link
                link_scraped = True

            # exceptions to prevent crashes if the element in not present or loaded yet
            except (NoSuchElementException, StaleElementReferenceException):
                continue

        if link_scraped:
            # removes empty lines
            text = [line for line in scraped_text if line]
            message_text = ""
            for line in text[1:31]:
                message_text += line + "\n"

            if len(message_text) == 0:
                showinfo(title="No text has been extracted!",
                         message="Please try another Xpath")
            else:
                answer = askyesno(
                    title="Extracted text!",
                    message=
                    ("Is this the text you wanted to extract?\n"
                     "Note: at most first 30 lines are displayed.\n"
                     "Selecting 'Yes' will continue the extracting process.\n"
                     "Selecting 'No' will prompt you to insert new Xpath.\n\n"
                     f"{message_text}"))
                if answer:
                    return True

            user_input = askstring(title="Please insert the xpath",
                                   prompt="Xpath?:")
            if not user_input:
                sys.exit()

        if link_skipped:
            showerror(
                title="Link extraction timeout!",
                message=
                "Either the link or the xpath are invalid, please try again.")
            sys.exit()


def scrape_links(driver: WebDriver, number_links: int, link_list: list[str],
                 xpath: str) -> tuple[list[str], list[str]]:
    """Loads links via textise.net and attempts to scrape them
    via the provided Xpath. If the Xpath element was not found in 15 seconds,
    the link will be skipped and later appended to a .txt file"""
    scraped_text = []
    discarded_links = []

    with alive_bar(number_links, spinner="classic",
                   title="Link processing") as progress_bar:

        # iterating over links, and loading them on www.textise.net
        for link in link_list:
            new_link = "https://www.textise.net/showText.aspx?strURL=https%253A" + link
            driver.get(new_link)
            original_link = "https:" + link

            timer_start = perf_counter()

            # scraping all text from links
            link_scraped = False
            link_skipped = False

            while not link_scraped and not link_skipped:
                try:
                    timer_end = perf_counter()
                    time_elapsed = timer_end - timer_start

                    # check if the link is invalid or inaccessible in some other way
                    if time_elapsed > 15:
                        discarded_links.append(original_link)
                        # updates progress bar
                        progress_bar()  # pylint: disable=not-callable
                        link_skipped = True

                    page_source = driver.find_element(by=By.XPATH, value=xpath)
                    page_source = page_source.text
                    text = page_source.split("\n")
                    scraped_text.append(original_link)
                    scraped_text.extend(text)

                    # sleep so that the CloudFlare protection triggers as infrequently as possible
                    progress_bar()  # pylint: disable=not-callable
                    sleep(round(uniform(0.9, 1.3), 10))
                    link_scraped = True

                # exceptions to prevent crashes if the element in not found
                except (NoSuchElementException,
                        StaleElementReferenceException):
                    continue

    return scraped_text, discarded_links


def process_and_save_scraped_text(scraped_text: list[str],
                                  discarded_links: list[str],
                                  current_dir: str):
    """This function uses pandas and regex to clean scraped text
    and then save it to either a .xlsx or .txt file.
    Additionally it saves discarded links to a separate .txt file"""

    with catch_warnings():
        filterwarnings("ignore", category=UserWarning)
        df = DataFrame(scraped_text, columns=["temp_header"])

        # removes leading and trailing spaces
        df = df["temp_header"].str.strip()

        # removes protected emails
        df.replace("\[email protected\]", None, inplace=True, regex=True)  # pylint: disable=anomalous-backslash-in-string

        # removes scraped image names (format [Image: Name of the image])
        df.replace("\[Image.*\]", None, inplace=True, regex=True)  # pylint: disable=anomalous-backslash-in-string

        text_cleaning = askyesno(
            title="Cleaning",
            message=
            ("Would you like to clean extracted data?\n"
             "Warning: This will remove all lines that contain only numbers, "
             "measurements, and other non-translatable text."),
            icon="warning")

        if text_cleaning:
            # further cleaning that removes a lot of SI measurements along with numerical values
            df.replace(
                (
                    "(?i)^(([\W\d_x])+?(([kdcm]|[kmg]|[dcml]|[tgmkb]|"  # pylint: disable=anomalous-backslash-in-string
                    "[NVAWP]){1,2}|Mpix|RPM){0,1}){1,3}?$"),
                None,
                inplace=True,
                regex=True)  # ?case arg

        link_removal = askyesno(
            title="Link removal",
            message=
            ("Would you like to remove links from which text was extracted?\n"
             "Warning: Doing so will make it impossible to know "
             "from where individual data was extracted."),
            icon="warning")

        if link_removal:
            df.replace("^https:\S+$", None, inplace=True, regex=True)  # pylint: disable=anomalous-backslash-in-string

        # removes any additional leading and trailing spaces if they were created during cleaning
        df = df.str.strip()

        #drops empty rows
        df.replace('', None, inplace=True)
        df.dropna(how="any", inplace=True)

        output_file_name = asksaveasfilename(
            title="Please save extracted text",
            defaultextension=".xlsx",
            filetypes=[("Excel file", "*.xlsx"), ("Text file", "*.txt")])

        file_extension = splitext(output_file_name)[1]

        if file_extension == ".xlsx":
            df.to_excel(output_file_name, index=False, header=False)

        if file_extension == ".txt":
            df.to_csv(output_file_name, index=False, header=False)

        # saves discarded links to a file
        if len(discarded_links) > 0:
            answer = askyesno(
                title="Discarded links",
                message=(f"Number of discarded links {len(discarded_links)}. "
                         "Would you like to save them to a file?"))
            if answer:
                path = current_dir + r"/discarded_links.txt"
                with open(path, "w", encoding='utf-8') as txt_file:
                    txt_file.write("Discarded links:\n")
                    txt_file.write("\n".join(discarded_links))

        # opens saved file
        system(rf'"{output_file_name}"')


def site_translation():
    """Translates whole websites or any list of links
    (currently .xml and .txt files are supported as inputs).
    Scraping is done via Xpath, and user is required to enter it manually.
    Recommended to use 'https://www.xml-sitemaps.com' to get all links that compose a site,
    otherwise just use a .txt file.
    All links are then forwarded to 'https://www.textise.net'
    so that their text forms could be scraped via Selenium."""

    root = create_program_mainloop(transparent_icon_location="icon.ico")

    processed_link_list, discarded_links, current_dir = find_suitable_file(
        root)

    first_link = processed_link_list[0]
    number_links = len(processed_link_list)

    driver = Chrome(options=custom_chrome_options())

    if check_xpath(driver, first_link):
        # scrapes the rest of the links
        scraped_text, discarded_links = scrape_links(driver, number_links,
                                                     processed_link_list,
                                                     "/html/body/div[5]")

        process_and_save_scraped_text(scraped_text, discarded_links,
                                      current_dir)

    driver.quit()


if __name__ == "__main__":
    site_translation()
