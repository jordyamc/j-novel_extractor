import requests
import json
import os
import dotenv
from playwright.sync_api import sync_playwright

config = dotenv.dotenv_values(".env")


def purge_token(login_path):
    with open(login_path, "r") as file:
        login_data = json.loads(file.read()) | {}
        login_data["token"] = ""
        login_data["userId"] = ""
    with open(login_path, "w") as file:
        file.write(json.dumps(login_data))


def check_login(login_path) -> bool:
    if os.path.exists(login_path):
        with open(login_path, "r") as file:
            login_data = json.loads(file.read()) | {}
            token_cookie = {'Cookie': f'access_token={login_data["token"]}; userId={login_data["userId"]}'}
        ping = requests.get("https://labs.j-novel.club/app/v1/me", headers=token_cookie)
        return ping.status_code != 401
    else:
        return False


def login_credentials(login_path):
    print("Credentials required\n\n")
    email = config.get("EMAIL", None) or input("Email: ")
    password = config.get("PASSWORD", None) or input("Password: ")
    login_data = {"email": email, "password": password, "token": "", "userId": ""}
    with open(login_path, "w") as file:
        file.write(json.dumps(login_data))


def login(login_path) -> bool:
    if not os.path.exists(login_path):
        login_credentials(login_path)
    else:
        with open(login_path, "r") as file:
            login_data = json.loads(file.read()) | {}
        if "email" not in login_data or "password" not in login_data:
            login_credentials(login_path)
        elif login_data["token"] != "" or login_data["userId"] != "":
            if check_login(login_path):
                return True
    print("\nTrying to login...\n")
    with open(login_path, "r") as file:
        login_data = json.loads(file.read()) | {}
    with sync_playwright() as p:
        browser = p.firefox.launch()
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://j-novel.club/login")
        page.get_by_placeholder("Email Address").fill(login_data["email"])
        page.get_by_placeholder("Password").fill(login_data["password"])
        page.locator("div.type-solid:nth-child(3)").click()
        page.wait_for_timeout(2000)
        cookies = context.cookies("https://j-novel.club")
        try:
            user_id = list(filter(lambda x: x["name"] == "userId", cookies))[0]["value"]
            access_token = list(filter(lambda x: x["name"] == "access_token", cookies))[0]["value"]
            if user_id != "" and access_token != "":
                login_data["userId"] = user_id
                login_data["token"] = access_token
                with open(login_path, "w") as file:
                    file.write(json.dumps(login_data))
                    print("Logged in successfully")
                return True
        except Exception:
            print("Error while trying to login")
            os.remove(login_data)
            return False
