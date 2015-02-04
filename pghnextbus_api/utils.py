import math
import re
import geojson

from datetime import datetime
from itertools import groupby
from pytz import timezone
from whoosh.index import open_dir
from whoosh.qparser import QueryParser

from pghbustime import BustimeError

def shash(s):
    """Hash function to try and group inbound and outbound stops together by
    removing various descriptive tokens (e.g. nearside, opp, past, at) from the
    stop name. 
    
    For example:
    >>> shash("Forbes Ave past Morewood") == shash("Forbes Ave opp Morewood")
    True
    """
    
    replace = [" Ave", " Blvd", " St", " Rd", " FS", " Dr", " Pl", "(farside)", "(nearside)", " opp ", " past ", " at ", " ", "  "]
    STATION = "Station"
    STOP = "stop"
    name = s.strip()
    
    if STATION in name.lower() and STOP in name.lower():
        name = name.split()
        name = " ".join(name.split(" ")[0:name.split(" ").index("Station")+1])
        
    for token in replace:
        name = name.replace(token, "")
        
    return hash(name.lower().strip())
    
def standardize_stop_name(name):
    remove = re.compile(r"(?:\s+(?:Ave|Blvd|St|Rd|Dr|Pl|Way|FS|NS)(?:\s+|$))|(?:\(farside\)|\(nearside\))", re.IGNORECASE)
    replace = re.compile(r"\s+(?:opp|past|at)\s+", re.IGNORECASE)
    edgecases = re.compile(r"(?:Ave [A-Z])\s")
    CONJUNCTION = " + "
    AT = " @ "

    if "station" not in name.lower():
        if '#' in name.lower():
            name = replace.sub(AT, name)
        elif edgecases.findall(name):
            pass
        else:
            name = replace.sub(CONJUNCTION, name)
    
        name = remove.sub(' ', name)

    return name.strip()

def search(query):
    """Search the stopindex for `query` using Whoosh."""
    from info import IDX_NAME
    
    ix = open_dir(IDX_NAME)
    parser = QueryParser("name", ix.schema)
    q = parser.parse(query)

    with ix.searcher() as s:
        results = s.search(q, limit=100)
        if not results:
            resp = []
        else:
            resp = [(r['name'], r['location'], r['sid']) for r in results]
    
    return resp        

def haversine(origin, destination, km=False):
    """Haversine distance formula over a sphere. Defaults to miles."""
    
    KM_MILE = 0.621371192
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371 # km

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c
    if km:
        return d
    else:
        return d * KM_MILE
    
def geojsonGrouped(stops, coord, n):
    """Group stops together by tokens in the name. For example, the stops
    `X St at Y Ave` and `X St opp Y Ave` would be treated as separate in the
    database, but should be lumped together for display."""
        
    def delta_sq(a, b): return (a[0] - b[0])**2 + (a[1] - b[1])**2
    
    # 3. Sort by distance and get the `n` closest.
    raw_features = sorted(stops, key=lambda s: haversine(map(float, s[1]), coord))[0:n]
    grouped_features = []
    
    for stop in raw_features:
        sid = stop[0]
        lat, lng = map(float, stop[1])
        name = stop[2]
        miToStop = haversine(map(float, stop[1]), coord)
        miToStop = round(miToStop, 3)
                
        grouped_features.append(geojson.Feature(
            geometry = geojson.Point((lng, lat)),
            properties = {
                'stopId': sid,
                'name': name,
                'miToStop': miToStop,
                'marker-size': 'medium',
                'marker-symbol': 'bus',
                'marker-color': '#fa0'                    
            }
        ))
    
    # 6. Return a FeatureCollection.
    grouped_features = sorted(grouped_features, key=lambda ft: ft['properties']['miToStop'])
    resp = geojson.FeatureCollection(grouped_features)
    return geojson.dumps(resp)        
    
def geojsonFind(results):
    """Generate GeoJSON for stops found in search results."""
    
    results = sorted(results, key=lambda r: r[0])
    grouped = groupby(results, lambda r: shash(r[0]))
    grouped_features = []
    
    for namehash, stopiter in grouped:
        stops = list(stopiter)
        
        if len(stops) <= 1:
            s = stops[0]
            sids = s[2]
            lat, lng = s[1][0], s[1][1]
            name = s[0]
        else:
            n = len(stops)
            sids = "multi:{}".format(",".join(s[2] for s in stops))
            lat = sum(float(s[1][0]) for s in stops) / n
            lng = sum(float(s[1][1]) for s in stops) / n
            name = stops[0][0]
            
        grouped_features.append(geojson.Feature(
            geometry = geojson.Point(map(float, (lng, lat))),
            properties = {
                'stopId': sids,
                'name': name,
                'marker-size': 'medium',
                'marker-symbol': 'bus',
                'marker-color': '#fa0'}                                    
        ))
    resp = geojson.FeatureCollection(grouped_features)        
    return geojson.dumps(resp)
    
def geojsonBus(bus):
    """Create GeoJSON for a bus object."""
    
    if type(bus.route) in [str, unicode]:
        markercolor = "#fa0"
    else:
        markercolor = "#{}".format(bus.route.color[1:6:2])    

    try: 
        return geojson.Feature(
                geometry = geojson.Point(bus.location[::-1]),
                properties = {
                    'vid': bus.vid,
                    'speed': bus.speed,
                    'heading': bus.heading,
                    'pattern': bus.patternid,
                    'destination': bus.destination,
                    'route': str(bus.route),
                    'lastupdated': str(bus.timeupdated),
                    'u_lastupdated': bus.timeupdated.strftime("%s"),
                    'next_stop': bus.next_stop.stop.name,
                    'marker-size': 'medium',
                    'marker-symbol': 'bus',
                    'marker-color': markercolor}
            )
    except:
        pass    

def geojsonOnRoute(buslist):
    """Return a FeatureCollection of all busses in `buslist`."""
    from info import CACHE
    
    busses = []
    for bus in buslist:
        if bus:
            ckey = "_onroute_bus_{}".format(bus.vid)            
            cached = CACHE.get(ckey)
            if not cached:
                feature = geojsonBus(bus)
                if feature:
                    CACHE.set(ckey, feature, time=25)
            else:    
                feature = cached
                
            if feature: busses.append(feature)
    return geojson.FeatureCollection(busses)    
    

def formatPrediction(p, usejson=False):
    """Turn a prediction object into a useful tuple for display."""
    FT_PER_MILE = 5280.0
    
    # ETA absolute time to relative time
    eta = (datetime.now(timezone("US/Eastern")) - p.eta).total_seconds() / -60.0
    eta = int(round(eta, 0))
    
    # Distance (ft) to distance (mi)
    dist = round(p.dist_to_stop / FT_PER_MILE, 1)
    
    if usejson:
        if 0 <= eta <= 10:
            displayClass = 'soon'
        elif 10 < eta <= 25:
            displayClass = 'kinda-soon'     
        else:
            displayClass = 'later'    
            
        direction = p.direction.capitalize()
        if p.is_arrival:
            direction = "{} departure".format(direction)
        resp = {
            'route': p.route,
            'destination': p.destination,
            'direction': p.direction.capitalize(),
            'eta': eta,
            'dist': dist,
            'vid': p.bus.vid,
            'display': displayClass
        }
        return resp
    else:
        return (p.route, p.destination, eta, dist, p.bus.vid)   
    