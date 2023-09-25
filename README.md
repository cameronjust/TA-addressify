
# ###################################
# TA-addressify Splunk addon


## About
This addon provides a custom search command for interracting with www.addressify.com.au APIs.

> Addressify is an address information site. The API endpoint used by this addon is "Info"

Ref: https://www.addressify.com.au/documentation/

* Author: Cameron Just
* Version: 1.0.6
* Splunkbase URL: n/a
* Source type(s): n/a
* Has index-time operations: No
* Input requirements: None
* Supported product(s): Search Heads

## Usage
On installation you will need to go to the apps setup page and enter your API key. 

Once setup just run any search which contains address information and feed them into the custom search command.

Usage:

>  \<search  command  with  ip  address\> | addressify field=[field_name_with_address]

Example: 

> | makeresults count=10 | eval address_data = if((random()%3) == 1, "186 Given Terrace, Paddington QLD 4064", "67 Castlemaine St, Milton QLD 4064") | addressify field=address_data

## Clearing KVStore

/opt/splunk/bin/splunk clean  kvstore -app TA-addressify -collection addressify_cache


## Troubleshooting

Try this search to see what sort of errors might be thrown by addressify.py script that runs the search command.

index=_internal source=*addressify*


## Developer Tips

Setup pages use a ridiculous number of files so make sure you edit them all when making changes. This is the most painful part of the whole app creation. Good luck!!!
 * bin/addressify_setup_handler.py - Writes conf files to local/addressify.conf and stores the API key in the password store
 * default/restmap.conf - Defines the Splunk REST endpoints related to configurations
 * default/data/ui/views/setup_page.xml - Renders the form for entering setup config in the web GUI
 * appserver/static/setup_page.css - Make config page pretty
 * appserver/static/setup_page.js - Javascript which pulls the existing app config from Splunk via a call to Splunk REST endpoints
 * default/web.conf - Allows the setup endpoints to be visible externally so the javascript on the configuration page can poll the API for previously configred settings

The search commands that actually does all the useful things use less files
 * default/commands.conf - Tells Splunk about the search command
 * bin/addressifypoll.py - Runs the search command


Troubleshooting errors with setup page not saving correctly
index=_internal source=*TA-addressify_setuphandler.log

If things arenot working with setup pages make sure you have a default/addressify.conf as there are issues with unconfigured apps.

Try to get to the endpoint for the config files
https://192.168.64.60:8089/servicesNS/nobody/TA-addressify/configs/conf-addressify/addressify_config?output_mode=json

## Changelog

* 1.0.0 - Initial development (2022-05-30)
* 1.0.1 - Fixed issue with setup completion not being detected (2022-05-31)
* 1.0.2 - Fixed bug with proxy server logging of success (2022-05-31)
* 1.0.3 - Updated Splunklib and fixed some python upgrade readiness issues (2022-06-07) - https://github.com/splunk/splunk-sdk-python
* 1.0.4 - Added additional exception checking and search.bnf fixes (2022-06-08)
* 1.0.5 - More sanity checking for optional boolean parameters (2022-06-15)
* 1.0.6 - Fixed a bug with proxy server configs

## ToDo

- [x] Try to work out why the setup page submission as is_configured doesn't seem to stick till a restart.
- [ ] Include option for modifying the cache expiry date
- [x] Ensure functionality exists for no KVStore Usage
- [ ] Improvements to Error Reporting


## Splunk App Inspect Results
