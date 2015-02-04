import os
import pylibmc
from sqlitedict import SqliteDict
from pghbustime import BustimeAPI
try:
    import cPickle as pickle
except:
    import pickle

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  
DB_NAME = os.path.join(BASE_DIR, "paac.db")
PICKLE_NAME = os.path.join(BASE_DIR, "paac.stops.pickle")
IDX_NAME = os.path.join(BASE_DIR, "stop_index")

routes = SqliteDict(DB_NAME, tablename='routes')
#stops = SqliteDict(DB_NAME, tablename='stops')
with open(PICKLE_NAME) as f: stops = pickle.load(f)
patterns = SqliteDict(DB_NAME, tablename='patterns')

# memcache
def getmemcache():    
    servers = os.environ.get('MEMCACHIER_SERVERS', None)
    user = os.environ.get('MEMCACHIER_USERNAME', '')
    pw = os.environ.get('MEMCACHIER_PASSWORD', '')
    
    if servers and servers[0] != '':
        # Probably heroku/production
        servers = servers.split(',')
        return pylibmc.Client(servers, binary=True,
                    username=user, password=pw,
                    behaviors={"tcp_nodelay": True,
                               "ketama": True,
                               "no_block": True,})

    else:
        # Local instance of Memcache (not heroku)
        servers = ['127.0.0.1:11211'] 
        return pylibmc.Client(servers, binary=True)

CACHE = getmemcache()