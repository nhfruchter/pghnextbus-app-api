from flask import Flask, request, abort
from flask.ext.compress import Compress
from flask.ext.cors import CORS

from functools import wraps

from pghbustime import BustimeAPI
import info

app = Flask(__name__)
# gzip compression
Compress(app)
# Enable the CORS header
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config.update(
    # Databases
    routes = info.routes,
    stops = info.stops,
    patterns = info.patterns,
    
    # Port Authority API key
    apiKey = "API KEY GOES HERE",
    apiGood = True,
    
    # General options
    maxStops = 125,
    minSearch = 3,
    maxNearest = 12
)
app.config.update(
    api = BustimeAPI(app.config.get('apiKey')),
    cur_routes = [ (rt, app.config['routes'][rt]['name']) for rt in sorted(app.config['routes'].keys())]
)

# Load the API key
with open('local-api-key.txt') as f:    
    app.config.update(
        localAPIKey = f.read()
    )

# Stupid simple API authentication. 
def require_appkey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.args.get('key') and request.args.get('key') == app.config['localAPIKey']:
            return view_function(*args, **kwargs)
        else:
            abort(401)
    return decorated_function
    
from . import views

