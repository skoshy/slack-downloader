#!/usr/bin/env python

# 
# slack-downloader
# Author: Enrico Cambiaso
# Email: enrico.cambiaso[at]gmail.com
# GitHub project URL: https://github.com/auino/slack-downloader
# 

import requests
import json
import argparse
import calendar
import errno
import sys
import os
import time
from datetime import datetime, timedelta
from pprint import pprint # for debugging purposes

################################################################
################################################################
################################################################

# Instatiate vars, they'll be populated in the main method
TOKEN = ""
CHANNELS = []

# output main directory, without slashes
OUTPUTDIR = "data"

# enable debug?
DEBUG = True

# enable extremely verbose debug?
EXTREME_DEBUG = False

# --- --- --- --- ---
#  CONFIGURATION END
# --- --- --- --- ---

# constants

# Slack base API url
API = 'https://slack.com/api'

# program directory
MAINDIR = os.path.dirname(os.path.realpath(__file__))+'/'

# useful to avoid duplicate downloads
TIMESTAMPFILE = MAINDIR+"offset.txt"
CONFIGFILE = MAINDIR+"config.json"

# Memos
MEMO_USERS = {}
MEMO_CHANNELS = {}
MEMO_GROUPS = {}

# format a response in json format
def response_to_json(response):
	try:
		res = response.json
		foo = res['ok']
		return res
	except: # different version of python-requests
		return response.json()

# file renaming function
def get_local_filename(basedir, filename, user, id, timestamp):
	# converting date from epoch time to readable format
	date = convert_timestamp_to_date(timestamp)
	# splitting filename to file extension
	filename, file_extension = os.path.splitext(filename)
	# retrieving full filename with path and returning it
	return basedir+'/'+str(timestamp)+'-'+id+file_extension

def convert_timestamp_to_date(timestamp):
	return time.strftime('%Y%m%d_%H%M%S', time.localtime(float(timestamp)))

# get saved timestamp of last download
# API Token: see https://api.slack.com/custom-integrations/legacy-tokens
def get_config():
	global TOKEN, CHANNELS

	try:
		in_file = open(CONFIGFILE,"r")
		text = in_file.read()
		in_file.close()
		configJson = json.loads(text)

		# Now let's populate vars
		TOKEN = configJson['token']
		if 'SLACK_TOKEN' in os.environ:
			TOKEN = os.environ['SLACK_TOKEN'] # override slack token if passed in as environ var

		CHANNELS = configJson["channels"]
	except Exception, e:
		if DEBUG: print str(e)

# save the timestamp of the last download (+1), in order to avoid duplicate downloads
def set_timestamp(ts):
	try:
		out_file = open(TIMESTAMPFILE,"w")
		out_file.write(str(ts))
		out_file.close()
		return True
	except Exception, e:
		if DEBUG: print str(e)
		return False

# get saved timestamp of last download
def get_timestamp():
	try:
		in_file = open(TIMESTAMPFILE,"r")
		text = in_file.read()
		in_file.close()
		return int(text)
	except Exception, e:
		if DEBUG: print str(e)
		set_timestamp(0)
		return None

# download a file to a specific location
def download_file(url, local_filename, basedir):
	try:
		os.stat(basedir)
	except:
		os.mkdir(basedir)
	try:
		print "Saving to", local_filename
		headers = {'Authorization': 'Bearer '+TOKEN}
		r = requests.get(url, headers=headers)
		with open(local_filename, 'wb') as f:
			for chunk in r.iter_content(chunk_size=1024):
				if chunk: f.write(chunk)
	except: return False
	return True

# get channel name from identifier
def get_channel_name(id):
	if id in MEMO_CHANNELS:
		responseAsJson = MEMO_CHANNELS[id]
		if DEBUG and EXTREME_DEBUG: print('Channel in Memo - '+responseAsJson['channel']['name']+' - '+id)
	else:
		url = API+'/channels.info'
		data = {'token': TOKEN, 'channel': id }
		response = requests.post(url, data=data)
		responseAsJson = response_to_json(response)
		MEMO_CHANNELS[id] = responseAsJson
	if DEBUG and EXTREME_DEBUG: pprint(responseAsJson)
	return responseAsJson['channel']['name']

# get group name from identifier
def get_group_name(id):
	if id in MEMO_GROUPS:
		responseAsJson = MEMO_GROUPS[id]
		if DEBUG and EXTREME_DEBUG: print('Group in Memo - '+responseAsJson['group']['name']+' - '+id)
	else:
		url = API+'/groups.info'
		data = {'token': TOKEN, 'channel': id }
		response = requests.post(url, data=data)
		responseAsJson = response_to_json(response)
		MEMO_GROUPS[id] = responseAsJson
	if DEBUG and EXTREME_DEBUG: pprint(responseAsJson)
	return responseAsJson['group']['name']

# get user name from identifier
def get_user_name(id):
	if id in MEMO_USERS:
		responseAsJson = MEMO_USERS[id]
		if DEBUG and EXTREME_DEBUG: print('User in Memo - '+responseAsJson['user']['name']+' - '+str(id))
	else:
		url = API+'/users.info'
		data = {'token': TOKEN, 'user': id }
		response = requests.post(url, data=data)
		responseAsJson = response_to_json(response)
		MEMO_USERS[id] = responseAsJson
	if DEBUG and EXTREME_DEBUG: pprint(responseAsJson)
	return responseAsJson['user']['name']

# request files
def make_requester():
	list_url = API+'/files.list'

	def all_requester(page):
		print('Requesting all files')
		data = {'token': TOKEN, 'page': page}
		ts = get_timestamp()
		if ts != None: data['ts_from'] = ts
		response = requests.post(list_url, data=data)
		if response.status_code != requests.codes.ok:
			print('Error fetching file list')
			sys.exit(1)
		return response_to_json(response)

	return all_requester

# main function
if __name__ == '__main__':
	# retrieving absolute output directory
	OUTPUTDIR = MAINDIR+OUTPUTDIR
	get_config()
	# creating main output directory, if needed
	try:
		os.stat(OUTPUTDIR)
	except:
		os.mkdir(OUTPUTDIR)
	page = 1
	users = dict()
	file_requester = make_requester()
	ts = None
	while True:
		json = file_requester(page)
		if not json['ok']: print('Error', json['error'])
		fileCount = len(json['files'])
		#print 'Found', fileCount, 'files in total'
		if fileCount == 0: break
		for f in json["files"]:
			try:
				if DEBUG and EXTREME_DEBUG: pprint(f) # extreme debug
				filename = f['name']
				timestamp = str(f['timestamp'])
				user = users.get(f['user'], get_user_name(f['user']))
				# isChannelMessageGroup = False
				if len(f['channels']) > 0:
					channel = get_channel_name(f['channels'][0])
					channelId = f['channels'][0]['id']
				elif len(f['groups']) > 0:
					channel = get_group_name(f['groups'][0])
					channelId = f['groups'][0]['id']
				else:
					print "No channel/group for file", f['id']
					continue
				# isChannelMessageGroup = channel.startsWith('mpdm-')
				if channel not in CHANNELS: # and not isChannelMessageGroup
					print "["+channel+"] File not in approved channels list", f['id']
					continue
				# if isChannelMessageGroup:
				# 	channel = str(channel) + '-' + str(channelId)
				file_url = f["url_private_download"]
				file_id = f["id"]
				basedir = OUTPUTDIR+'/'+channel
				local_filename = get_local_filename(basedir, filename, user, file_id, timestamp)
				if os.path.exists(local_filename):
					print "["+channel+"] File already exists - "+str(file_url)
				else:
					print "["+channel+"] Downloading file '"+str(file_url)+"'"
					download_file(file_url, local_filename, basedir)
				if ts == None or float(date) > float(ts): ts = date
			except Exception, e:
				if DEBUG: print str(e)
				else: print "Problem during download of file", f['id']
				pass
		page = page + 1
	if ts != None: set_timestamp(int(ts)+1)
	print('Finished.')
