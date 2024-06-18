import platform
from pathlib import Path


def configdir(app_name, create=True):
    MACOS, LINUX, WINDOWS = (platform.system() == x for x in ['Darwin', 'Linux', 'Windows'])

    # Return the appropriate config directory for each operating system
    if WINDOWS:
        path = Path.home() / 'AppData' / 'Local' / app_name
    elif MACOS:  # macOS
        path = Path.home() / 'Library' / 'Application Support' / app_name
    elif LINUX:
        path = Path.home() / '.config' / app_name
    else:
        raise ValueError(f'Unsupported operating system: {platform.system()}')

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return str(path)
