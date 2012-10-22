"""
Copyright (c) 2011, 2012, Regents of the University of California
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions 
are met:

 - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the
   distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL 
THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES 
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) 
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, 
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED 
OF THE POSSIBILITY OF SUCH DAMAGE.
"""
"""
@author Stephen Dawson-Haggerty <stevedh@eecs.berkeley.edu>
"""
"""Driver to poll data from a Weather Underground weather station,
using their xml api.

Optional Parameters: 

"Address" : URI to fetch data from.  The driver will GET the URL,
and add a query parameter with the station id.

"ID" [default KCABERKE25] : wunderground station id

"Rate" [default 60] : number of seconds between polls.
"""

import urllib2
import rfc822
from xml.dom.minidom import parse, parseString
from xml.parsers.expat import ExpatError

from twisted.internet import reactor
from twisted.python import log
from smap import driver, util

def get_val(dom, key):
    v = dom.getElementsByTagName(key)[0].firstChild.nodeValue
    return v

class WunderGround(driver.SmapDriver):
    def setup(self, opts):
        self.url = opts.get("Address", 
                            "http://api.wunderground.com/weatherstation/WXCurrentObXML.asp")
        self.id = opts.get("ID", "KCABERKE25")
        self.rate = int(opts.get("Rate", 60))
        self.last_time = 0
        self.metadata_done = False
        
        self.add_timeseries("/wind_dir", "deg")
        self.add_timeseries("/wind_speed", "m/s", data_type="double")
        self.add_timeseries("/wind_gust", "m/s", data_type="double") 
        self.add_timeseries("/humidity", "rh")
        self.add_timeseries("/temperature", "C", data_type="double") 
        self.add_timeseries("/pressure", "mb", data_type="double")   
        self.add_timeseries("/dew_point", "C", data_type="double")   

    def start(self):
        util.periodicSequentialCall(self.update).start(self.rate)

    def update(self):
        try:
            url = self.url + "?ID=" + self.id
            fh = urllib2.urlopen(url, timeout=10)
        except urllib2.URLError, e:
            log.err("URLError getting reading: [%s]: %s" % (url, str(e)))
            return
        except urllib2.HTTPError, e:
            log.err("HTTP Error: [%s]: %s" % (url, str(e)))
            return

        try:
            dom = parse(fh)
        except ExpatError, e:
            log.err("Exception parsing DOM [%s]: %s" % (url, str(e)))
            return

        try:
            reading_time = rfc822.parsedate_tz(get_val(dom, "observation_time_rfc822"))
            reading_time = int(rfc822.mktime_tz(reading_time))
        except Exception, e:
            log.err("Exception finding time [%s]: %s" % (url, str(e)))
            return

        if reading_time > self.last_time:
            self.add('/wind_dir', reading_time, int(get_val(dom, "wind_degrees")))
            self.add('/wind_speed', reading_time, float(get_val(dom, "wind_mph")))
            self.add("/wind_gust", reading_time, float(get_val(dom, "wind_gust_mph")))
            self.add("/humidity", reading_time, int(get_val(dom, "relative_humidity")))
            self.add("/temperature", reading_time, float(get_val(dom, "temp_c")))
            self.add("/pressure", reading_time, float(get_val(dom, "pressure_mb")))
            self.add("/dew_point", reading_time, float(get_val(dom, "dewpoint_c")))
            last_time = reading_time

        if not self.metadata_done:
            self.metadata_done = True
            self.set_metadata('/', {
                    'Extra/StationType' : get_val(dom, "station_type"),
                    'Extra/StationID' : get_val(dom, "station_id"),
                    'Location/Latitude' : get_val(dom, "latitude"),
                    'Location/Longitude': get_val(dom, "longitude"),
                    'Location/Altitude': get_val(dom, "elevation"),
                    'Location/Uri' : get_val(dom, "link"),
                    'Location/City' : get_val(dom, "city"),
                    'Location/State' : get_val(dom, "state"),
                    })

        dom.unlink()
