from flask import Response, render_template, request, redirect, url_for

from . import app, apihelper, require_appkey
import info
import json
import geojson
import md5

##################### INTERFACE PAGES #########################

@app.route('/')
def home():
    return render_template('home.html')
    
##################### API ENDPOINTS ###########################

@app.route('/api/availableroutes')
def apiavailableroutes():
    ckey = '_available_routes'
    if not info.CACHE.get(ckey):
        resp = {'available': app.config['cur_routes']}
        info.CACHE.set(ckey, json.dumps(resp))
    
    resp = info.CACHE.get(ckey)    
    return Response(resp, mimetype='text/json')

@app.route('/api/stopdb/checksum')
def apistopschecksum():
    ckey = '_stops_checksum'
    if not info.CACHE.get(ckey):
        checksum = md5.md5(repr(app.config['stops'])).hexdigest()
        resp = json.dumps({'checksum': checksum})
        info.CACHE.set(ckey, resp)
    
    resp = info.CACHE.get(ckey)    
    return Response(resp, mimetype='text/json')
    
@app.route('/api/stopdb/db')
@require_appkey
def apiappstops():
    ckey = "_stops"
    if not info.CACHE.get(ckey):
        checksum = md5.md5(repr(app.config['stops'])).hexdigest()
        resp = json.dumps({'checksum': checksum, 'stops': app.config['stops']})
        info.CACHE.set(ckey, resp)
        
    resp = info.CACHE.get(ckey)    
    return Response(resp, mimetype='text/json')

@app.route('/api/stop/<sid>')
@require_appkey
def apistop(sid):
    """Get predictions for stop `sid` in JSON form."""    
    ckey = "_stop_{sid}".format(sid=sid)
    if not info.CACHE.get(ckey):
        resp = apihelper.stop(sid, app.config)
        info.CACHE.set(ckey, resp, time=20)
    
    resp = info.CACHE.get(ckey)        
    return Response(resp, mimetype='text/json')
    
@app.route('/api/near/<lat>/<lng>')
@require_appkey
def apinearby(lat, lng):
    """Get a list of stops near `(lat, lng)` in geoJSON form."""
    ckey = "_nearby_{}".format(hash((lat,lng)))
    maxNearest = request.args.get('n') or 10
    if not info.CACHE.get(ckey):
        resp = apihelper.nearby(lat, lng, app.config, maxNearest)
        info.CACHE.set(ckey, resp)
        
    resp = info.CACHE.get(ckey)    
    return Response(resp, mimetype='text/json')    

@app.route('/api/find/<q>')    
def apifind(q):
    """Return GeoJSON of search results for query `q`."""
    ckey = "_find_{}".format(hash(q))
    if not info.CACHE.get(ckey):
        results = apihelper.find(q) 
        info.CACHE.set(ckey, results)

    resp = info.CACHE.get(ckey)
    return Response(resp, mimetype='text/json')
    
@require_appkey
@app.route('/api/onroute/<rt>')    
def apiallbusses(rt):
    """GeoJSON endpoint to get all vehicles on `rt`."""
    return apihelper.busseson(rt, app.config)

@app.route('/api/bus/<vid>')
@require_appkey
def apibuslocation(vid):
    """GeoJSON endpoint to get data on vehicle `vid`."""    
    ckey = "_vehicle_{}".format(vid)
    
    if not app.config.get('disabled_api'):
        if not info.CACHE.get(ckey):
            resp = apihelper.bus(vid, app.config['api'])
            info.CACHE.set(ckey, resp, time=15)

        resp = info.CACHE.get(ckey)
    else:
        resp = json.dumps({'error': 'API over limit.'})
        
    return Response(resp, mimetype='text/json')
    
@app.route('/api/pattern/<pid>')
@require_appkey
def apipattern(pid):
    """Return the GeoJSON for a certain route pattern `pid`."""
    
    if pid in app.config['patterns']:
        ckey = "_pattern_{}".format(pid)
        if not info.CACHE.get(ckey):
            resp = geojson.dumps(app.config['patterns'][pid])
            info.CACHE.set(ckey, resp)

        resp = info.CACHE.get(ckey)    
        return Response(resp, mimetype='text/json')
    else:
        resp = json.dumps({'error': 'Pattern not found.'})
        return Response(resp, mimetype='text/json', status=404)
        
#### API Status #######
@app.route('/api/toggledisable/1af796463e74f21cb77c1b8f20e44a1a')
@require_appkey
def disablemessage():
    if not app.config.get('disabled_api'):
        app.config['disabled_api'] = True
    else:
        app.config['disabled_api'] = not app.config['disabled_api']
    
    resp = {'disabled': app.config['disabled_api']}    
    return redirect(url_for('apidisabled'))
    
@app.route('/api/isdisabled')
def apidisabled():
    resp = {'disabled': app.config.get('disabled_api') or False}
    return Response(json.dumps(resp), mimetype='text/json')
    