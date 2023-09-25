#!/usr/bin/env python
# coding=utf-8

import sys, os, json
import logging
import requests
import urllib.parse

# For detailed exeption handling
import linecache
import inspect


#set up logging to this location
from logging.handlers import TimedRotatingFileHandler
LOG_FILENAME = os.path.join("addressify_api_cli.log")

# Set up a specific logger
logger = logging.getLogger('spur')

#default logging level , can be overidden in stanza config
logger.setLevel(logging.DEBUG)

#log format
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

# Add the daily rolling log message handler to the logger
# handler = TimedRotatingFileHandler(LOG_FILENAME, when="d",interval=1,backupCount=5)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

##########################################
# Function definitions
# 
#   _____ _   _ _   _  ____ _____ ___ ___  _   _   ____  _____ _____ ____  
#  |  ___| | | | \ | |/ ___|_   _|_ _/ _ \| \ | |  |  _ \| ____|  ___/ ___| 
#  | |_  | | | |  \| | |     | |  | | | | |  \| |  | | | |  _| | |_  \___ \ 
#  |  _| | |_| | |\  | |___  | |  | | |_| | |\  |  | |_| | |___|  _|  ___) |
#  |_|    \___/|_| \_|\____| |_| |___\___/|_| \_|  |____/|_____|_|   |____/ 

# More detailed exception reporting
def detailed_exception():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    return 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)


logger.info("Doing it")

try:

    logger.info("Doing it")
    address = "67 Castlemaine St, Milton QLD 4064"
    api_token = "03cfffffffffffffffffa4b4691"
    basicSanityCheck = False
#    proxies = {'http': 'http://webproxy:8080', 'https': 'http://webproxy:8080'}
    proxies = None

    # Check for something here if you want
    if True:
        basicSanityCheck = True

    if basicSanityCheck:
        logger.debug("address '%s' passed sanity check" % address)

        # Poll API if a valid IP address
        # curl "https://api.addressify.com.au/addresspro/info?api_key=03c38ddf-72c7-4784-8579-0555555555&term=67%20Castlemaine%20St%2C%20Milton%20QLD%204064"

        # Add any headers required here.
        # Addressify doesn't need them but leaving code here if someone wants to use this app as a template to access other API vendors
#        headers = {'Token': spur_token}
        headers = {}

        url = 'https://api.addressify.com.au/addresspro/info?api_key=%s&term=%s' % (api_token,urllib.parse.quote(address))
        logger.debug("Calling API with %s" % url)

        session = requests.Session()
        if proxies:
            session.proxies = self.proxies

        result = session.get(url, headers=headers, verify=False)
        result_json = json.loads(result.text)

#        response, content = rest.simpleRequest(url, sessionKey=config_parameters["sessionKey"], getargs={'output_mode': 'json'})
#        result_json = json.loads(content)
        
        logger.debug("status=%d,message=Call returned" % result.status_code)
        logger.debug("payload=%s" % result_json)

        for key in result_json:
            logger.debug("%s=%s" % (key,result_json[key]))
        
        # Output Specific fields as a test to see if these can be referenced directly.
#        logger.debug("Country Code=%s" % (result_json["location"]["country"]))
        

except Exception as e:
    logger.error("Oh noes")
    logger.error(detailed_exception())
    