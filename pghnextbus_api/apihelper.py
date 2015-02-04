from . import utils
from . import app
from pghbustime import Stop, Route, BustimeAPI, BustimeError, Bus
from pghbustime.interface import APILimitExceeded

import json
import geojson
from flask import Response

## /api/stop

def singlestop(sid, config, multipart=False):
    """Return JSON for a single stop `sid`."""
    
    # Create a new stop object to get at the prediction.
    stopObject = Stop.get(config['api'], sid)
    
    # Get predictions.
    try:
        stopPredictions = list(stopObject.predictions())
    except BustimeError as e:
        if type(e) is APILimitExceeded:
            app.config['disabled_api'] = True
            
        stopPredictions = False
    
    # Create formatted tuples with prediction info for display.
    if stopPredictions:
        predictions = [utils.formatPrediction(p, usejson=True) for p in stopPredictions]
    else:
        predictions = [] 
         
    resp = {
        'predictions': predictions,
        'vids': "-".join([p['vid'] for p in predictions])
        }
        
    if not multipart:
        resp['stopInfo'] = {
            'name': config['stops'][sid][-1],
            'loc': config['stops'][sid][1]
        }

    return resp
    
def multistop(sid, config):
    """Generate a JSON response for multiple routes."""
    
    stops = sid.replace("multi:", "").split(",")    
    responses = [singlestop(sid, config, multipart=True) for sid in stops]
    predictions = reduce(list.__add__, (r['predictions'] for r in responses) )
    predictions = sorted(predictions, key=lambda p: p['eta'])
    joined = {
        'predictions': predictions,
        'vids': "-".join([p['vid'] for p in predictions])
    }
    
    return joined
    
def stop(sid, config):
    if not config.get('disabled_api'):
        if "multi:" in sid:
            resp = multistop(sid, config)
        else:
            resp = singlestop(sid, config)
    else:
        resp = {
            'predictions': [
                {"dist":0.0,
                "destination":"API OVER LIMIT",
                "display":"soon",
                "eta":"",
                "vid":0000,
                "route":"API Error",
                "direction":"We've exceeded our daily allotment for Port Authority data requests."}
            ],
            'vids': "9999"
        }
        resp['stopInfo'] = {
            'name': config['stops'][sid][-1],
            'loc': config['stops'][sid][1]
        }
        
    return json.dumps(resp)    
        
    
## /api/near
    
def nearby(lat, lng, config, maxNearest=10):
    """Get a list of stops from `stopdb` near `(lat, lng)` in GeoJSON form,
    limiting to `limit` results."""
    maxNearest = int(maxNearest)
    try:
        loc = map(float, (lat, lng))
        resp = utils.geojsonGrouped(config['stops'].values(), loc, maxNearest)
    except:
        resp = json.dumps({'error': 'Invalid lat/lng pair.'})
    
    return resp
    
## /api/find    
    
def find(q):
    """Collect and foramt results for query `q`."""
    results = utils.search(q)
    return utils.geojsonFind(results)
    
## /api/onroute    
    
def busseson(rt, config):
    """Return GeoJSON or error to get all busses on route `rt`."""
    
    rt = rt.split(',')
    valid = all(r in config['routes'] for r in rt)
    if valid:
        busobjs, offroute = [], []
        for r in rt:
            try: 
                buslist = list(Route.get(config['api'], r).busses)
                busobjs.append(buslist)
            except:
                offroute.append(r)
                
        if busobjs:        
            busobjs = reduce(list.__add__, busobjs)            
            onroute = utils.geojsonOnRoute(busobjs)
            onroute['inactive'] = offroute
            resp = geojson.dumps(onroute)
            resp = Response(resp, mimetype='text/json')
        else:
            resp = json.dumps({'error': 'This route has no busses.'})        
            resp = Response(resp, mimetype='text/json', status=404)
    else:
        resp = json.dumps({'error': 'This route is not available or does not exist.'})    
        resp = Response(resp, mimetype='text/json', status=404)
    
    return resp
    
## /api/bus    
def bus(vid, api):
    from datetime import datetime
    """Return GeoJSON for current bus position with ID `vid`."""
    notfound = {
        'type': 'Feature',
        'geometry': {"type": "Point", "coordinates": [0,0]},
        'properties': {
            'marker-size': 'medium',
	        'marker-symbol': 'bus',
	        'marker-color': '#aaa',
            'u_lastupdated': datetime.now().strftime("%s"),
            'title': 'Location data temporarily unavailable.'
        }
    }    

    try:
        # Get geoJSON from the API response.
        busobj = Bus.get(api, vid)
        resp = utils.geojsonBus(busobj)
    except BustimeError as e:
        # Return a "bus not found" geoJSON response.
        if type(e) is APILimitExceeded:
            app.config['disabled_api'] = True        
        resp = notfound
    return geojson.dumps(resp)

def nextstops(preds, api):
    if preds.get('predictions'):
        vids = [vehicle['vid'] for vehicle in preds['predictions']]
        nexts = {}
        for vid in vids:
            try:
                nexts[vid] = Bus.get(api, vid).next_stop.stop.name
            except BustimeError as e:
                if type(e) is APILimitExceeded:
                    app.config['disabled_api'] = True                                
                continue
        return nexts
    else:
        return False    
    