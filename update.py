from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from os import path as ospath, environ, remove
from subprocess import run as srun
from importlib.metadata import distributions
from requests import get as rget
from dotenv import load_dotenv

if ospath.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

if ospath.exists('rlog.txt'):
    remove('rlog.txt')

basicConfig(format="[%(asctime)s] [%(levelname)s] - %(message)s",
            datefmt="%d-%b-%y %I:%M:%S %p",
            handlers=[FileHandler('log.txt'), StreamHandler()],
            level=INFO)

# Optional: pull config.env from a private URL (e.g. a gist) before anything else
CONFIG_FILE_URL = environ.get('CONFIG_FILE_URL')
if CONFIG_FILE_URL and len(CONFIG_FILE_URL) > 0:
    try:
        res = rget(CONFIG_FILE_URL)
        if res.status_code == 200:
            with open('config.env', 'wb+') as f:
                f.write(res.content)
            log_info('Config file downloaded from CONFIG_FILE_URL')
        else:
            log_error(f"Failed to download config.env {res.status_code}")
    except Exception as e:
        log_error(f"CONFIG_FILE_URL: {e}")

load_dotenv('config.env', override=True)

if len(environ.get('BOT_TOKEN', '')) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

if environ.get('UPGRADE_PACKAGES', 'False').lower() == 'true':
    packages = sorted({d.metadata['Name'] for d in distributions() if d.metadata['Name']})
    srun("pip install --upgrade " + ' '.join(packages), shell=True)

# ---------------------------------------------------------------------------
# Auto-update from a git repo is OFF by default.
# This is a stripped-down bot: if it pulled the original upstream repo on start-up,
# all removed features would come back. Only runs when UPSTREAM_REPO is set explicitly
# in the environment / config.env (point it at YOUR OWN repo, never the old upstream).
# ---------------------------------------------------------------------------
UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '').strip()
UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '').strip() or 'main'

if UPSTREAM_REPO:
    # `git add . / reset --hard` below can overwrite tracked files. A live sqlite session
    # (bot.session + -wal/-shm) caught in that ends up as an empty db, so keep a copy.
    from glob import glob
    from shutil import copy2
    _kept = {}
    for _f in glob('*.session*'):
        try:
            _tmp = f"/tmp/keep_{_f}"
            copy2(_f, _tmp)
            _kept[_f] = _tmp
        except Exception as e:
            log_error(f"Could not back up {_f}: {e}")

    if ospath.exists('.git'):
        srun(["rm", "-rf", ".git"])

    update = srun([f"git init -q \
                     && git config --global user.email bot@localhost \
                     && git config --global user.name bot \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"], shell=True)

    for _f, _tmp in _kept.items():
        try:
            copy2(_tmp, _f)
            remove(_tmp)
        except Exception as e:
            log_error(f"Could not restore {_f}: {e}")

    if update.returncode == 0:
        log_info('Successfully updated with latest commits !!')
    else:
        log_error('Update failed! Check UPSTREAM_REPO / UPSTREAM_BRANCH.')
else:
    log_info('UPSTREAM_REPO is empty -> running the code that is deployed (no auto-update).')
