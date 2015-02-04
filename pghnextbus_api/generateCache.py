"""Generate a database of stops for every route available."""

from sqlitedict import SqliteDict
from whoosh import index
from whoosh.fields import TEXT, ID, STORED, Schema

import os
import re
import cPickle as pickle
import sqlite3
import logging
from itertools import groupby

from pghbustime import BustimeAPI, Route
import pghbustime.utils as utils
from utils import shash, standardize_stop_name

def all_routes(api, dbname):    
    """Create an SqliteDict with all routes and their stops."""
    
    log = logging.getLogger(__name__)
    
    # All routes with tracking
    rtdicts = api.routes()['route']
    allroutes = SqliteDict(dbname, tablename="routes")
    
    for rtdict in rtdicts:
        rtobject = Route.fromapi(api, rtdict)
        log.debug("Processing route {}".format(rtobject.name))

        if rtobject.number in allroutes:
            log.debug("SKIP: Route already in database.")
            continue
        else:            
            rtdict = {
                'name': rtobject.name,
                'number': rtobject.number,
                'inbound': {s.id: {'location': s.location, 'name': s.name} for s in rtobject.inbound_stops},
                'outbound': {s.id: {'location': s.location, 'name': s.name} for s in rtobject.outbound_stops}
            }
            allroutes[str(rtobject.number)] = rtdict
    
    log.debug("Committing changes...")
    allroutes.commit()
    
    return dbname    

def all_stops(api):
    """Generate a pickle of all stops."""
    
    log = logging.getLogger(__name__)
    logging.basicConfig(level=logging.DEBUG)
    
    rtdicts = api.routes()['route'] # All active routes on the realtime system.
    stopset = set()
    allstops = {}
    
    # Whoosh index
    schema = Schema(sid=TEXT(stored=True), name=TEXT(stored=True), location=STORED())
    indexname = "stop_index"
    if not os.path.exists(indexname): 
        os.mkdir(indexname)
        ix = index.create_in(indexname, schema)
    else:
        ix = index.open_dir(indexname)    
    writer = ix.writer()
    
    log.debug("Generating stop database.")
    
    # Loop through all the routes to get at stops (API has weird structure)
    for rtdict in rtdicts:
        if rtdict['rt'] not in allstops:
            rtobject = Route.fromapi(api, rtdict)        
            # Add all stops on the route to the set
            for s in rtobject.inbound_stops + rtobject.outbound_stops:
                stop = (s.id, s.location, s.name)
                stopset.add(stop)
        
    nchanges = 0    
    log.debug("Generating search index.")
    for stop in stopset:
        nchanges +=1
        allstops[stop[0]] = stop


    # Switch to display groupings
    allstops = group_stops(allstops)
    

    for stop in allstops.values():
        writer.update_document(sid=unicode(stop[0]), name=stop[2], location=stop[1])                
    writer.commit()

    # And create pickle too
    log.debug("Pickling db...")
    export = dict(allstops)
    with open("paac.stops.pickle", "w") as f:
        pickle.dump(allstops, f)
    
    # And create app db
    log.debug("Creating app database...")
    # create_app_db(allstops, already_grouped=True)
    
    return nchanges
    
def patterns(api, dbname):
    Route.get(api, 88)
    patterns = SqliteDict(dbname,  tablename="patterns")
    
    for rt in Route.all_routes.values():
        color = rt.color
        rtpatterns = rt.patterns['ptr']
        if type(rtpatterns) != list:
            rtpatterns = [rtpatterns]
            # Outputs first element, not list of length one for some reason
        for pt in rtpatterns:
            print pt['pid']
            patterns[pt['pid']] = utils.patterntogeojson(pt, color)
    patterns.commit()
    
def create_app_db(stops, name='stops.db', already_grouped=False):
    
    schema = """CREATE TABLE if not exists "stops" (
    "id" TEXT PRIMARY KEY NOT NULL,
    "lat" REAL NOT NULL,
    "lng" REAL NOT NULL,
    "name" TEXT)"""

    # Set up SQLite connections    
    APP_DB = name
    conn = sqlite3.connect(APP_DB)
    cur = conn.cursor()
    
    # Create table if it doesn't exist
    print "Creating table..."
    cur.execute(schema)
    conn.commit()
    
    if not already_grouped:
        # Group stops
        print "Grouping stops..."
        stops = group_stops(stops)

    # Copy stops dict into database
    n = len(stops.values())
    for i, row in enumerate(stops.values()):
        id, lat, lng, name = row[0], row[1][0], row[1][1], row[2]
        statement = "INSERT INTO stops VALUES (\"{id}\", {lat}, {lng}, \"{name}\")".format(id=id,lat=lat,lng=lng,name=name)
        cur.execute(statement)
        if i % 500 == 0 or i == n-1:
            print "{}/{} - {}".format(i+1, n, statement)
    
    print "Committing changes..."
    conn.commit()        
    print "Done."   
    
def group_stops(stops):
    """Groups a stops dictionary."""
    stops = stops.values()

    # Sort by name grouping for itertools
    stops = sorted(stops, key=lambda s: shash(s[2]))
    grouped = groupby(stops, lambda s: shash(s[2]))

    grouped_stops = {}    
    for namehash, pointiter in grouped:
        points = list(pointiter)
        n = len(points)
        
        # There is only one stop for that intersection name
        if n == 1:
            pt = points[0]
            lat, lng = map(float, pt[1])
            sids = pt[0]
            name = standardize_stop_name(pt[2])
        # There are multiple stops for that intersection name
        elif n > 1:
            sids = "multi:{}".format(",".join(pt[0] for pt in points))
            # Average stop locations for the multistop
            lat = sum(float(pt[1][0]) for pt in points) / n
            lng = sum(float(pt[1][1]) for pt in points) / n
            name = standardize_stop_name(points[0][2])
        
        grouped_stops[sids] = (sids, (lat, lng), name)
        
    return grouped_stops    
            
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description="Generate a list of all bus routes and associated stops.")
    p.add_argument('key', metavar='APIKEY', help='Port Authority API key.')

    args = p.parse_args()
    api = BustimeAPI(args.key)
    
    logging.basicConfig(level=logging.DEBUG)
    #
    # all_routes(api, "./paac.db")
    # all_stops(api)
    patterns(api, "./paac.db")
    
    
        

    


        
