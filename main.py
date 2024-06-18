import pathlib

import requests
import json
import os
import validators
import argparse
import subprocess
import dotenv
from configdir import configdir
from login import login, purge_token
from pathlib import Path
from pathvalidate import sanitize_filepath
from ebooklib import epub
from bs4 import BeautifulSoup

config = dotenv.dotenv_values(".env")
parser = argparse.ArgumentParser(
    description="Downloads book parts from J-Novel and combine them into an epub book"
)
parser.add_argument("-u", "--url", dest="direct_url", help="Specify a novel url to extract")
parser.add_argument("-a", "--all", dest="auto_type", action="store_const", const="all", help="Extract all catchup and followed")
parser.add_argument("-ac", "--all-catchup", dest="auto_type", action="store_const", const="catchup", help="Extract all catchup novels")
parser.add_argument("-af", "--all-followed", dest="auto_type", action="store_const", const="follow", help="Extract all followed novels")
parser.add_argument("-o", "--output", dest="output", default="output", type=pathlib.Path, help="Output directory")
args = parser.parse_args()
token_cookie = {}

config_path = configdir("J-Novel Extractor")
login_path = Path(config_path, "login.data")
checked = []
notification_token = config.get("NOTIFICATION_TOKEN", "")
notifications = {}


def notify():
    global notifications
    if len(notifications) == 0:
        return
    if notification_token:
        body = "**J-Novel Extractor**\n\n"
        changed = False
        for key in notifications:
            item = notifications[key]
            if item["isNew"] or any([item["vols"][x]["epub"] or len(item["vols"][x]['parts']) for x in item["vols"]]):
                changed = True
                title = f"[{item['name']}]({item['link']})"
                if item["isNew"]:
                    title += " ⭐"
                body += f"{title}\n"
                for vol_name in item["vols"]:
                    vol = item["vols"][vol_name]
                    if vol["epub"] or len(vol["parts"]):
                        vol_body = f"{' ' * 4}-{vol_name}"
                        vol_body += "\n"
                        if vol["epub"]:
                            vol_body += f"{' ' * 8}•**Epub created**\n"
                        else:
                            vol_body += f"{' ' * 8}•Parts {', '.join(vol['parts'])} downloaded\n"
                        vol_body += "\n"
                        body += vol_body
        if changed:
            body = body.replace('"', "'")
            subprocess.run(f"apprise -i markdown -b \"{body}\" {notification_token}")
    notifications = {}


def extract_series(data_type):
    series = []
    with requests.get("https://j-novel.club/series", headers=token_cookie) as info:
        soup = BeautifulSoup(info.text, "html.parser")
        json_text = soup.select_one("script#__NEXT_DATA__").string
        series_data = json.loads(json_text)["props"]["pageProps"]["seriesList"]
        if series_data["success"]:
            data = series_data["data"]["series"]
            for serie in data:
                if serie["type"] == 2:
                    continue
                if data_type == "catchup" and not serie["catchup"]:
                    continue
                if data_type == "follow" and not serie["following"]:
                    continue
                series.append(
                    {
                        "name": serie["title"],
                        "link": "https://j-novel.club/series/" + serie["slug"]
                    }
                )
        else:
            if series_data["code"] == 410:
                purge_token(login_path)
            main()
    return series


def main_menu():
    os.system("cls")
    print("Select a series to extract...\n")
    print("1- Catchup")
    print("2- Followed")
    print("3- All")
    selection = input("\nExtract: ")
    if selection.isnumeric():
        if selection == "1":
            check_selection("catchup")
            notify()
        elif selection == "2":
            check_selection("follow")
            notify()
        elif selection == "3":
            check_selection("catchup", True)
            check_selection("follow", True)
            notify()
        else:
            main_menu()
    elif validators.url(selection):
        download_series(selection)
        notify()
    else:
        main_menu()


def check_selection(check_type, bypass=False):
    os.system("cls")
    print(f"Check {check_type}...\n")
    series = extract_series(check_type)
    if not bypass:
        print("Select a series to extract...\n")
        for index, serie in enumerate(series):
            print(f"{index + 1}- {serie['name']}")
        print(f"{len(series) + 1}- All")
        selection = input("\nExtract: ")
    if not bypass and (not selection.isnumeric() or int(selection) > len(series) + 1):
        check_selection(check_type, bypass)
    else:
        if bypass or int(selection) == (len(series) + 1):
            for serie in series:
                download_series(serie['link'])
                print("")
            os.system("cls")
            print(f"Downloaded or updated {len(series)} books")
        else:
            select = series[int(selection) - 1]
            download_series(select['link'])


def download_series(link):
    os.system("cls")
    global notifications
    if link in checked:
        print("Link already checked")
        return
    with requests.get(link, headers=token_cookie) as info:
        soup = BeautifulSoup(info.text, "html.parser")
        name = str(soup.select_one("div[id] h1").string)
        print(f"Downloading books from {name}...\n")
        output_dir = Path(args.output, sanitize_filepath(name))  # /Novel name/
        notification_data = {
            "name": name,
            "link": link,
            "isNew": not output_dir.exists(),
            "vols": {}
        }
        os.makedirs(output_dir, exist_ok=True)
        data_path = Path(output_dir, "base_data.json")  # /Novel name/base_data.json
        if not data_path.exists():
            metadata = soup.select("div.aside-buttons div.text")
            base_data = {
                "link": link,
                "title": str(soup.select_one("div[id] h1").string),
                "title_jp": str(soup.select_one("div[id] h3").string),
                "author": str(metadata[0].string),
                "illustrator": str(metadata[1].string),
                "translator": str(metadata[2].string),
                "editor": str(metadata[3].string),
                "tags": list(map(lambda tag: str(tag.string), soup.select("div.aside-buttons a.link[href*=tag] div.text")))
            }
            with open(data_path, "w") as out:
                out.write(json.dumps(base_data))
        else:
            with open(data_path, "r") as data_input:
                base_data = json.loads(data_input.read())
        for root_index, volume in enumerate(soup.select("div[id^=volume-]")):
            vol_name = str(volume.select_one("h2 > a").string)
            vol_path = sanitize_filepath(Path(output_dir, vol_name))  # /Novel name/Volume #/
            notification_data["vols"][vol_name] = {
                "epub": False,
                "parts": []
            }
            cover_path = Path(vol_path, "cover.jpg")  # /Novel name/Volume #/cover.jpg
            book_path = Path(vol_path, sanitize_filepath(f"{vol_name}.epub"))  # /Novel name/Volume #/volume #.epub
            base_data_path = Path(vol_path, "data.xhtml")  # /Novel name/Volume #/data.xhtml
            description = str(volume.select_one("div.collapsed p").string)
            release = volume.select_one(".collapsed .label .text").string
            parts = volume.select("a[href^=\\/read], div.unavailable")[1:]
            available = 0
            print(f"     {vol_name}: {len(parts)} parts")
            if not book_path.exists():
                book = epub.EpubBook()
                if os.path.exists(cover_path):
                    with open(cover_path, "rb") as cover_in:
                        book.set_cover("cover.jpg", cover_in.read())
                if base_data_path.exists():
                    os.remove(base_data_path)
                for index, downloadable in enumerate(parts):
                    types = downloadable.get_attribute_list("class")
                    part_num = str(downloadable.select("span")[-1].string)
                    part_path = Path(vol_path, f"part {part_num}")  # /Novel name/Volume #/part #/
                    part_data_path = Path(part_path, "data.xhtml")  # /Novel name/Volume #/part #/data.xhtml
                    img_path = Path(part_path, "static")  # /Novel name/Volume #/part #/static/
                    if part_data_path.exists():
                        print(f"         Part {part_num}...", end=" ")
                        available += 1
                        with open(part_data_path, "r", errors="ignore") as in_stream:
                            with open(base_data_path, "a", errors="ignore") as out_stream:
                                out_stream.write(in_stream.read())
                        for d_image in os.listdir(img_path):
                            with open(Path(img_path, d_image), "rb") as bys:
                                img_item = epub.EpubImage(uid=os.path.split(d_image)[0], file_name=f"static/{d_image}", media_type="image/jpg", content=bys.read())
                                book.add_item(img_item)
                        print("exist")
                    else:
                        if "unavailable" in types:
                            print(f"         Part {part_num}... unavailable")
                        elif "expired" in types:
                            print(f"         Part {part_num}... expired")
                        else:
                            print(f"         Part {part_num}...", end=" ")
                            notification_data["vols"][vol_name]["parts"].append(part_num)
                            notifications[name] = notification_data
                            available += 1
                            os.makedirs(part_path, exist_ok=True)
                            os.makedirs(img_path, exist_ok=True)
                            part_base = requests.get('https://j-novel.club' + downloadable["href"], headers=token_cookie)
                            chap_soup = BeautifulSoup(part_base.text, "html.parser")
                            part_base = requests.get(chap_soup.select_one("iframe[src*=embed]")["src"] + "/data.xhtml", headers=token_cookie)
                            chap_soup = BeautifulSoup(part_base.text, "html.parser")
                            signature = chap_soup.select_one(".signature")
                            if signature is not None:
                                signature.decompose()
                            for img_index, img in enumerate(chap_soup.find_all("img")):
                                url = img["src"]
                                image_name = str(hash(url)) + f"{img_index}.jpg"
                                with open(Path(img_path, image_name), "wb") as img_out:
                                    bys = requests.get(url, headers=token_cookie).content
                                    if index == 0 and img_index == 0:
                                        with open(cover_path, "wb") as cover_out:
                                            cover_out.write(bys)
                                        book.set_cover("cover.jpg", bys)
                                        img.decompose()
                                    else:
                                        img_item = epub.EpubImage(uid=os.path.split(image_name)[0], file_name=f"static/{image_name}", media_type="image/jpg", content=bys)
                                        img["src"] = f"static/{image_name}"
                                        book.add_item(img_item)
                                    img_out.write(bys)
                            with open(part_data_path, "wb") as data_out:
                                encoded = chap_soup.select_one("div.main").encode_contents(formatter="html")
                                data_out.write(encoded)
                                with open(base_data_path, "ab") as base_data_out:
                                    base_data_out.write(encoded)
                            print("done")
                if os.path.exists(base_data_path):
                    with open(base_data_path, "r", encoding="utf-8", errors="ignore") as base_data_in:
                        base_document = BeautifulSoup(f"<html><body>{base_data_in.read()}</body></html>", "html.parser")
                    create_epub = len(parts) == available
                    if create_epub:
                        print("         Creating epub...", end=" ")
                        if base_data['title'] == vol_name:
                            title = base_data['title']
                            alt_title = base_data['title_jp']
                        else:
                            title = f"{base_data['title']}: {vol_name}"
                            alt_title = f"{base_data['title_jp']}: {vol_name}"
                        book.set_title(title)
                        book.set_title(alt_title)
                        book.add_author(base_data["author"])
                        book.add_author(base_data["illustrator"], role="illustrator", uid="illustrator")
                        book.add_author(base_data["translator"], role="translator", uid="translator")
                        book.add_author(base_data["editor"], role="editor", uid="editor")
                        book.add_metadata("DC", "publisher", "J-novel Club")
                        book.set_language("en")
                        book.add_metadata("DC", "description", description)
                        book.add_metadata("DC", "date", f"{release}T06:00:00+00:00")
                        book.add_metadata(None, "meta", base_data['title'], {"property": "belongs-to-collection", "id": "c01"})
                        book.add_metadata(None, "meta", "series", {"refines": "#c01", "property": "collection-type"})
                        book.add_metadata(None, "meta", str(root_index + 1), {"refines": "#c01", "property": "group-position"})
                        for tag in base_data["tags"]:
                            book.add_metadata("DC", "subject", tag)
                        default_css = epub.EpubItem(uid="style_default", file_name="style/default.css", media_type="text/css", content=requests.get("https://m11.j-novel.club/style/novel-rough.css").content)
                        book.add_item(default_css)
                        chap_count = 0
                        chap_dict = {}
                        for tag in base_document.find("body").findAll(recursive=False):
                            if tag.name == "h1":
                                chap_count += 1
                                d = chap_dict.get(f"p{str(chap_count)}", {"title": "", "id": "", "subs": []})
                                id = f"t{chap_count}"
                                tag["id"] = id
                                d["title"] = tag.string
                                d["id"] = id
                                chap_dict[f"p{str(chap_count)}"] = d
                            d = chap_dict.get(f"p{str(chap_count)}", {"title": "", "subs": []})
                            if tag.name == "h2":
                                id = f"s{len(d['subs'])}"
                                tag["id"] = id
                                d['subs'].append({"name": str(tag.string), "id": id})
                        toc_links = []
                        chap_file_name = f"main.xhtml"
                        chapter = epub.EpubHtml(title=vol_name, file_name=chap_file_name, lang="en")
                        chapter.add_link(href="style/default.css", rel="stylesheet", type="text/css")
                        chapter.content = base_document.prettify('utf-8')
                        book.add_item(chapter)
                        for index, key in enumerate(chap_dict.keys()):
                            toc_links.append(
                                (epub.Link(f"{chap_file_name}#{chap_dict[key]['id']}", chap_dict[key]["title"], str(hash(chap_dict[key]['id']))),
                                 list(
                                     map(
                                         lambda sub: epub.Link(f"{chap_file_name}#{sub['id']}", sub["name"], str(hash(chap_file_name + "#" + sub["id"]))),
                                         chap_dict[key]["subs"]
                                     )
                                 )
                                 )
                            )
                        book.toc = toc_links
                        book.spine = [chapter]
                        book.add_item(epub.EpubNcx())
                        book.add_item(epub.EpubNav())
                        epub.write_epub(book_path, book)
                        notification_data["vols"][vol_name]["epub"] = True
                        notifications[name] = notification_data
                        print("done")
                    else:
                        print("         Skip creating epub, some parts unavailable")
                else:
                    print("         Skip creating epub, no data available")
            else:
                print("         Skip creating epub, book already downloaded")
        checked.append(link)


def main():
    global token_cookie
    os.system("cls")
    if not login(login_path):
        main()
    os.system("cls")
    with open(login_path, "r") as file:
        login_data = json.loads(file.read()) | {}
    token_cookie = {'Cookie': f'access_token={login_data["token"]}; userId={login_data["userId"]}'}
    if args.direct_url:
        if validators.url(args.direct_url):
            download_series(args.direct_url)
        else:
            print(f"Invalid url: {args.direct_url}")
    if args.auto_type:
        if args.auto_type == "all":
            check_selection("catchup", True)
            check_selection("follow", True)
        else:
            check_selection(args.auto_type, True)
        notify()
    else:
        main_menu()


main()
