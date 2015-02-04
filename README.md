# Pittsburgh Next Bus app backend
This is the back-end API service that proxies between the Port Authority API and the app in order to surface relevant, formatted information.

## Requirements
All requirements are listed in the `requirements.txt` folder. I recommend setting up a Python `virtualenv` and installing everything by using `pip`.

## Setup
1. Obtain a Port Authority API key.
2. Install requirements.
3. Generate the app database by running the `generateCache.py` file. This script takes one argument, which is your API key. This will take a little while and will spew a lot of output to your console.
4. Generate an API key so that you can access your local API by running `generateKey.py`.
5. Put your Port Authority API key in `__init__.py`.

