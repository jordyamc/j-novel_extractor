> [!IMPORTANT]
> This script requires to have an active subscription to [J-Novel Club](https://j-novel.club/subscribe)

> [!NOTE]
> The purpose of this script is to have a personal archive of parts and epub books for people that doesn't 
> have time to read the weekly releases from your favorite series

# Installation
### NodeJS
[Install NodeJS](https://nodejs.org/en/download/package-manager/current)

Install browser instance for playwright:

`npx playwright install firefox`

### Python
Install required libraries

`pip install -r requirements.txt`

# Usage
To run the script simply run:

`python main.py`

The script have an interactive menu to download specific, followed and/or catchup series .
You can also automatize actions with command line:

| Command             | Description                             |
|---------------------|-----------------------------------------|
| -h, --help          | Show help message                       |
| -u , --url          | Specify a novel url to extract          |
| -a, --all           | Extract all catchup and followed        |
| -ac, --all-catchup  | Extract all catchup novels              |
| -af, --all-followed | Extract all followed novels             |
| -o, --output        | Output directory (default is "/output") |

# Configuration
The script can be configured using a `.env` file, check the `.env.example` file to see more.
### Notifications
The script support [apprise notifications](https://github.com/caronc/apprise), edit the notification 
token in the `.env` file.

### Login
You can specify an email and password to skip the manual input when the script asks for it.