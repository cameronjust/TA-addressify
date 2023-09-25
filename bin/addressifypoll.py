#!/usr/bin/python
# -*- coding: utf-8 -*-

# Comment Ascii Art
# Ref Large: http://patorjk.com/software/taag/#p=display&f=Standard 
# Ref Small: http://patorjk.com/software/taag/#p=display&f=Calvin%20S

# Test for parsing errors with
# /opt/splunk/bin/splunk cmd python /opt/splunk/etc/apps/TA-addressify/bin/addressifypoll.py searchargs

# Logs
# tail -f /opt/splunk/var/log/splunk/TA-addressify_api.log

# Test Search
# | tstats  count FROM datamodel=Edgerouter.EdgerouterFirewall WHERE (nodename=EdgerouterFirewall.TrafficOUT.OUT_SYN "EdgerouterFirewall.SRC"="192.168.64.90") BY _time span=auto "EdgerouterFirewall.DST" | rename "EdgerouterFirewall.DST" as DST | dedup DST | addressifyipscan field="DST"

import sys, os, json, logging, inspect, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)))
import requests

# Used for building Query to API
import urllib.parse

import rivium_utils as utils

# For timers
import time


####
# Splunk VS Code Debugging - https://github.com/splunk/vscode-extension-splunk/wiki/Debugging
sys.path.append(os.path.join(os.environ['SPLUNK_HOME'],'etc','apps','SA-VSCode','bin'))
# import splunk_debug as dbg
#dbg.enable_debugging(timeout=25)
####


# Load up Splunklib (App inspect recommends splunklib goes into the appname/lib directory)
libPathName = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib'))
sys.path.append(libPathName)
from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
from splunklib.six.moves import range

# Splunk simple REST library ($SPLUNK_HOME/splunk/lib/python3.7/site-packages/splunk/rest)
import splunk.rest as rest

# Normal Splunk REST call
# def simpleRequest(path, sessionKey=None, getargs=None, postargs=None, method='GET', raiseAllErrors=False, proxyMode=False, rawResult=False, timeout=None, jsonargs=None, token=False):


##########################################
# Search Command Definition
# ╔═╗╔═╗╔═╗╦═╗╔═╗╦ ╦  ╔═╗╔═╗╔╦╗╔╦╗╔═╗╔╗╔╔╦╗  ╔╦╗╔═╗╔═╗╦╔╗╔╦╔╦╗╦╔═╗╔╗╔
# ╚═╗║╣ ╠═╣╠╦╝║  ╠═╣  ║  ║ ║║║║║║║╠═╣║║║ ║║   ║║║╣ ╠╣ ║║║║║ ║ ║║ ║║║║
# ╚═╝╚═╝╩ ╩╩╚═╚═╝╩ ╩  ╚═╝╚═╝╩ ╩╩ ╩╩ ╩╝╚╝═╩╝  ═╩╝╚═╝╚  ╩╝╚╝╩ ╩ ╩╚═╝╝╚╝

# https://github.com/splunk/splunk-sdk-python/blob/7645d29b7fc1166c554bf9a7a03f40a02529ccc4/splunklib/searchcommands/search_command.py#L97
# https://github.com/splunk/splunk-sdk-python/blob/7645d29b7fc1166c554bf9a7a03f40a02529ccc4/splunklib/searchcommands/streaming_command.py#L26

@Configuration(distributed=False)
class addressifypollCommand(StreamingCommand):
    """
     | addressifyipscan [field="ip"]]
     """

    # parameters specific to this addon
    field  = Option(name='field',  require=True)
    fullPayload  = Option(name='full_payload',  require=False, default="False")
    useCache = Option(name='use_cache',  require=False, default="True")
    forceCacheRefresh = Option(name='force_cache_refresh',  require=False, default="False")
    debugTimer = Option(name='debug_timer',  require=False, default="False") # Timer is good for seeing how long calls to KVstore or addressify take
    
    API_key = "MTA0xxxxxxxxxxxxxxxxxxxxxxxxxRTM="
    useKVStore = False
    debugLogging = False
    ignoreInternalIPs = True
    KVStore = "addressify_cache"
    daysToCache = 30
    dummyPrivateIpResponse = {"ip": "", "countryCode": "ZZ", "countryName": "ZZ", "type": 0, "organization": "Private or unnanounced IP", "block": 0}
    suppress_error = False
    proxies = {}

    # Some constants to make porting this app for other purposes easier
    splunkAppName = "TA-addressify"
    scriptName = os.path.basename(__file__)
    confFilename = "addressify"
    confStanza = "api_config"
    logLevel = logging.DEBUG
    logfileDescriptor = "api"
    appLogger = None
    # logLevel = logging.INFO

    # Retrieve configuration parameters
    # ╦  ╔═╗╔═╗╔╦╗  ╔═╗╔═╗╔╗╔╔═╗╦╔═╗╔═╗
    # ║  ║ ║╠═╣ ║║  ║  ║ ║║║║╠╣ ║║ ╦╚═╗
    # ╩═╝╚═╝╩ ╩═╩╝  ╚═╝╚═╝╝╚╝╚  ╩╚═╝╚═╝
    def loadConfigs(self):

        self.appLogger.debug("Loading configuration parameters")

        try:
            splunkSessionKey = self.metadata.searchinfo.session_key
            confSettings = utils.configLoad(self.splunkAppName,self.confFilename,splunkSessionKey)

            if "useKVStore" in confSettings: 
                if confSettings["useKVStore"] == "1":
                    self.useKVStore = True
                else:
                    self.useKVStore = False

                self.appLogger.info("%s,message=KVStore setting of %d found in local/%s.conf." % (utils.fileFunctionLineNumber(), self.useKVStore, self.confFilename))

            else:
                self.appLogger.warning("%s,message=No KV Store config found in local/%s.conf." % (utils.fileFunctionLineNumber(), self.confFilename))

            # Check if KVStore exists
            try:
                # Check KV Store Exists
                # curl -k -u admin:pass https://localhost:8089//servicesNS/nobody/TA-addressify/storage/collections/config/addressify_cache 

                KVStoreURI = "/servicesNS/nobody/%s/storage/collections/data/%s" % (self.splunkAppName,self.KVStore)
                response, content = rest.simpleRequest(KVStoreURI, sessionKey=splunkSessionKey, getargs={'output_mode': 'json'})
                if response.status == 200:                
                    self.appLogger.debug("%s,section=KVStoreCheck,response.status=%d,message=Found KVStore" % (utils.fileFunctionLineNumber(),response.status))
                else:
                    self.appLogger.debug("%s,section=KVStoreCheck,response.status=%d,message=KV Store not found : %s" % (utils.fileFunctionLineNumber(),response.status,response))

            except Exception:
                self.appLogger.error("%s,section=KVStoreCheck,message=Exception %s." % (utils.fileFunctionLineNumber(),utils.detailedException()))

            if "debugLogging" in confSettings: 
                if confSettings["debugLogging"] == "1":
                    self.debugLogging = True
                    self.appLogger.setLevel(logging.DEBUG)
                else:
                    self.debugLogging = False
                    self.appLogger.setLevel(logging.INFO)

                self.appLogger.info("%s,message=debugLogging setting of %d found in local/%s.conf." % (utils.fileFunctionLineNumber(), self.debugLogging, self.confFilename))

            else:
                self.appLogger.warning("%s,message=No debug config found in local/%s.conf." % (utils.fileFunctionLineNumber(),self.confFilename))

            # Loading the addressify.us API key
            self.API_key, responseStatus = utils.loadPassword(self.splunkAppName, self.confFilename, splunkSessionKey, "addressify_api_key")

            # Loading the proxy server config
            try:
                if "proxy_settings" in confSettings:
                    proxy_server = confSettings["proxy_settings"]

                    # Check if blank
                    if proxy_server.strip() != "":
                    
                        # append in http:// if it's missing
                        if not proxy_server.startswith("http"):
                            proxy_server = 'http://' + proxy_server
                        
                        try:
                            self.proxies = {'http': proxy_server, 'https': proxy_server}
                            response = requests.get("https://example.com/", proxies=self.proxies)
                            if response.status_code == 200:
                                self.appLogger.debug("%s,section=ProxyCheck,message=Proxy Test connection successful" % (utils.fileFunctionLineNumber()))
                            else:
                                self.appLogger.error("%s,section=ProxyCheck,message=Proxy server test connection to %s failed. Not setting a proxy server." % (utils.fileFunctionLineNumber(),proxy_server))
                                self.proxies = {}
                        except Exception:
                            self.appLogger.error("%s,section=ProxyCheck,message=Proxy server test connection to %s failed. Will skip use of proxy. Exception %s." % (utils.fileFunctionLineNumber(),proxy_server, utils.detailedException()))
                            self.proxies = {}
                            
            except Exception:
                self.appLogger.error("%s,section=ProxyCheck,message=Exception %s." % (utils.fileFunctionLineNumber(),utils.detailedException()))
                self.proxies = {}
            
            

        except Exception as e:
            self.appLogger.error("%s,message=Exception %s." % (utils.fileFunctionLineNumber(),utils.detailedException()))
            raise e
                    
    # Streaming Processor
    # ╔═╗╔╦╗╦═╗╔═╗╔═╗╔╦╗╦╔╗╔╔═╗  ╔═╗╦═╗╔═╗╔═╗╔═╗╔═╗╔═╗╔═╗╦═╗
    # ╚═╗ ║ ╠╦╝║╣ ╠═╣║║║║║║║║ ╦  ╠═╝╠╦╝║ ║║  ║╣ ╚═╗╚═╗║ ║╠╦╝
    # ╚═╝ ╩ ╩╚═╚═╝╩ ╩╩ ╩╩╝╚╝╚═╝  ╩  ╩╚═╚═╝╚═╝╚═╝╚═╝╚═╝╚═╝╩╚═
    def stream(self, events):
        #dbg.set_breakpoint()

        try:

            # Setup logger
            self.appLogger = utils.loggingSetup(self.splunkAppName,self.logfileDescriptor)
            self.appLogger.setLevel(logging.DEBUG)

            self.loadConfigs()
            self.appLogger.info('%s,addressifyCommand=%s', (utils.fileFunctionLineNumber(),self))

            #logger.info("Config Settings %s" % self._configuration)
            #logger.info("Headers %s" % self._input_header)
            
            # Use sessions as requested by addressify.com.au for HTTPS requests
            self.appLogger.info("%s,message=streaming started setting up session with addressify." % utils.fileFunctionLineNumber())
            session = requests.Session()
            session.proxies = self.proxies
            
            splunkSessionKey = self.metadata.searchinfo.session_key

            #################
            # Parse search command args. This probably belongs in an __init__ function
            
            # fullPayload
            if not type(self.fullPayload)==bool:
                if self.fullPayload.lower() == "true" or self.fullPayload.lower() == "1" or self.fullPayload.lower() == "yes":
                    self.appLogger.debug("%s,message=fullPayload argument is on (value=%s)." % (utils.fileFunctionLineNumber(), self.fullPayload))
                    self.fullPayload = True
                else:
                    self.appLogger.debug("%s,message=fullPayload argument is off (value=%s)." % (utils.fileFunctionLineNumber(), self.fullPayload))
                    self.fullPayload = False

            # useCache
            if not type(self.useCache)==bool:
                if self.useCache.lower() == "true" or self.useCache.lower() == "1" or self.useCache.lower() == "yes":
                    self.appLogger.debug("%s,message=useCache argument is on (value=%s)." % (utils.fileFunctionLineNumber(), self.useCache))
                    self.useCache = True
                else:
                    self.appLogger.debug("%s,message=useCache argument is off (value=%s)." % (utils.fileFunctionLineNumber(), self.useCache))
                    self.useCache = False

            # forceCacheRefresh
            if not type(self.forceCacheRefresh)==bool:
                if self.forceCacheRefresh.lower() == "true" or self.forceCacheRefresh.lower() == "1" or self.forceCacheRefresh.lower() == "yes":
                    self.appLogger.debug("%s,message=useCache argument is on (value=%s)." % (utils.fileFunctionLineNumber(), self.useCache))
                    self.forceCacheRefresh = True
                else:
                    self.appLogger.debug("%s,message=useCache argument is off (value=%s)." % (utils.fileFunctionLineNumber(), self.useCache))
                    self.forceCacheRefresh = False

            # debugTimer
            if not type(self.debugTimer)==bool:
                if self.debugTimer.lower() == "true" or self.debugTimer.lower() == "1" or self.debugTimer.lower() == "yes":
                    self.appLogger.debug("%s,message=debugTimer argument is on (value=%s)." % (utils.fileFunctionLineNumber(), self.debugTimer))
                    self.debugTimer = True
                else:
                    self.appLogger.debug("%s,message=debugTimer argument is off (value=%s)." % (utils.fileFunctionLineNumber(), self.debugTimer))
                    self.debugTimer = False

            # Counters
            eventsProcessed = 0
            addressifyCalls = 0
            cachedEntries = 0
            skippedInternalIPs = 0
            isPrivateIP = False
            errors = 0

            for event in events:
                
                if not self.field in event :
                    continue

                try:
                    address_query = event[self.field]
                    basicSanityCheck = False
                    
                    # Can put some sanity checking here if you want and set the basicSanityCheck=True. 
                    if True:
                        basicSanityCheck = True

                    # we're ready to poll
                    if basicSanityCheck:

                        # timer for performance testing
                        startTimer = time.perf_counter()
                            
                        self.appLogger.debug("%s,section=ipSanityCheck,passed=1,address_query=%s" % (utils.fileFunctionLineNumber(), address_query))

                        # Check KV Store for entry
                        self.appLogger.debug("%s,section=checkKvStore,address_query=%s" % (utils.fileFunctionLineNumber(), address_query))
                        hasKVStoreEntry = False
                        
                        # Should we ignore the cache?
                        if (self.useCache):
                            query = {"address_query": address_query}
                            resp = utils.queryKVStore(self.splunkAppName, splunkSessionKey, self.KVStore, query)
                            response = json.loads(resp.decode("utf-8"))
                            self.appLogger.debug("%s,section=KVStoreResponse,response=%s" % (utils.fileFunctionLineNumber(), response))

                            # Multiple sanity checks on the data
                            if response is not None:
                                if(isinstance(response,list)):
                                    if len(response) > 0:
                                        if 'date_modified' in response[0] and '_key' in response[0]:
                                            # Check if date_modified is still within valid cache time limit or if they passed force cache refresh as a search parameter
                                            if int(response[0]['date_modified']) > time.time() - (self.daysToCache*24*60*60) and not self.forceCacheRefresh:
                                                self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry still valid using it instead of looking up addressify for new one,date_modified=%s,_key=%s" % (utils.fileFunctionLineNumber(), response[0]['date_modified'], response[0]['_key']))
                                                hasKVStoreEntry = True

                                            # It's OLD purge from KV Store
                                            else:
                                                self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry expired we are going to delete it get a new one" % (utils.fileFunctionLineNumber()))
                                                utils.deleteKVStoreEntry(self.splunkAppName, splunkSessionKey, self.KVStore, response[0]['_key'])
                                        else:
                                            self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry reponse didn't have date_modified or _key field,response=%s" % (utils.fileFunctionLineNumber(),response[0]))
                                    else:
                                        self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry reponse was zero length" % (utils.fileFunctionLineNumber()))
                                else:
                                    self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry reponse wasn't a list" % (utils.fileFunctionLineNumber()))
                            else:
                                self.appLogger.debug("%s,section=KVStoreResponse,message=KVStoreEntry reponse didn't exist" % (utils.fileFunctionLineNumber()))

                
                            
                        if(hasKVStoreEntry):

                            # Increment Counter
                            cachedEntries = cachedEntries + 1

                            entry = response[0]['response']

                            # Marker field to tell if this result was cached from KVStore or not
                            event["addressify_cached"] = 1
                            
                            # Force base level fields into results in case they don't exist in the first record. This is needed due to a "feature" in Splunk
                            event["addressify_addressfull"] = ""
                            event["addressify_postcode"] = ""
                            event["addressify_suburb"] = ""
                            event["addressify_state"] = ""
                            event["addressify_latitude"] = ""
                            event["addressify_longitude"] = ""
                            event["addressify_valid"] = ""
                          
                            for key in entry:
                                
                                # Skip hostname, _user, _key or date_modified fields
                                if key=="_user" or key=="_key" or key=="date_modified": continue

                                # Add all remaining fields
                                self.appLogger.debug("%s,section=KVStoreReponseFieldParsing,%s=%s" % (utils.fileFunctionLineNumber(), key, entry[key]))
                                event["addressify_" + key.lower()] = entry[key]

                            # Throw in the full payload too
                            if self.fullPayload:
                                event["addressify_full_payload"] = entry

                            if self.debugTimer:
                                event["debug_timer"] = (time.perf_counter() - startTimer)*1000
                            

                        # Poll addressify.com.au for result
                        else:
                            try:
                                # Increment Counter
                                addressifyCalls = addressifyCalls + 1

                                # Marker field to tell if this result was cached from KVStore or not
                                event["addressify_cached"] = 0

                                # Poll API if a valid IP address
                                # curl "https://api.addressify.com.au/addresspro/info?api_key=03c38ddf-72c7-4784-8579-55555691&term=67%20Castlemaine%20St%2C%20Milton%20QLD%204064"

                                # Add headers here if required for auth (not needed for addressify)
#                                headers = {'Token': self.API_key}
                                headers = {}

                                
                                url = 'https://api.addressify.com.au/addresspro/info?api_key=%s&term=%s' % (self.API_key,urllib.parse.quote(address_query))
                                self.appLogger.debug("%s,section=addressifyCall,requestUrl=%s" % (utils.fileFunctionLineNumber(), url))

                                result = session.get(url, headers=headers, verify=False)
                                result_json = json.loads(result.text)

                                self.appLogger.debug("%s,section=reponseParsing,status=%d,message=Call returned" % (utils.fileFunctionLineNumber(), result.status_code))
                                self.appLogger.debug("%s,section=reponseParsing,payload=%s" % (utils.fileFunctionLineNumber(), result_json))

                                # Force base level fields into results in case they don't exist in the first record. This is needed due to a "feature" in Splunk
                                event["addressify_addressfull"] = ""
                                event["addressify_postcode"] = ""
                                event["addressify_suburb"] = ""
                                event["addressify_state"] = ""
                                event["addressify_latitude"] = ""
                                event["addressify_longitude"] = ""
                                event["addressify_valid"] = ""


                                for key in result_json:

                                    # Skip any fields we might not want from response
                                    if key=="skipthisfieldnotusedhere": continue

                                    # Add all remaining fields
                                    self.appLogger.debug("%s,section=reponseFieldParsing,%s=%s" % (utils.fileFunctionLineNumber(), key, result_json[key]))
                                    event["addressify_" + key.lower()] = result_json[key]

#                                    if (key == "block"):
#                                        event["addressify_block_desc"] = self.blockTranslate(result_json[key])

                                # Throw in the full payload too
                                if self.fullPayload:
                                    event["addressify_full_payload"] = result_json
                                

                                # Insert/Update addressify results to KV Store
                                # fields addressfull, postcode, suburb, state, lat, lon
                                record = {}
                                record["address_query"] = address_query
                                record["date_modified"] = int(time.time())
                                record["response"] = result_json
                                record["addressfull"] = event["addressify_addressfull"]
                                record["postcode"] = event["addressify_postcode"]
                                record["suburb"] = event["addressify_suburb"]
                                record["state"] = event["addressify_state"]
                                record["latitude"] = event["addressify_latitude"]
                                record["longitude"] = event["addressify_longitude"]
                                record["valid"] = event["addressify_valid"]
                                
 #                               record["block_desc"] = event["iphub_block_desc"]

                                utils.writeToKVStore(self.splunkAppName, splunkSessionKey, self.KVStore, record, keyFields = ["address_query"])

                                # Stop timer after kvstore written
                                if self.debugTimer:
                                    event["debug_timer"] = (time.perf_counter() - startTimer)*1000

                            except Exception as e:
                                self.appLogger.error("%s,section=addressifypolling,message=%s" % (utils.fileFunctionLineNumber(),utils.detailedException()))
                                if not self.suppress_error:
                                    raise e


                    else:
                        self.appLogger.warning("%s,section=SanityCheck,passed=0,address_query=%s" % (utils.fileFunctionLineNumber(), address_query))


                except Exception as e:
                    self.appLogger.error("%s,section=addressifypolling,message=%s" % (utils.fileFunctionLineNumber(),utils.detailedException()))
                    if not self.suppress_error:
                        raise e

                # Return enriched event back to Splunk
                eventsProcessed = eventsProcessed + 1
                yield event

            self.appLogger.info("%s,eventCount=%d,APICalls=%d,cachedEntries=%d,message=streaming ended" % (utils.fileFunctionLineNumber(),eventsProcessed,addressifyCalls,cachedEntries))

        except Exception as e:
            self.appLogger.error("%s,section=outerTry,message=%s" % (utils.fileFunctionLineNumber(),utils.detailedException()))
#            self.appLogger.error(utils.detailedException())
            raise e

# logger.debug("section=argumentsPassed,%s" % (sys.argv))

# for line in sys.stdin:
#    logger.debug("section=stdIn,%s" % (line))
    
dispatch(addressifypollCommand, sys.argv, sys.stdin, sys.stdout, __name__)

