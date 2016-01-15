#!/usr/bin/env python3
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

### CONFIGURATION START ###

# API Token: see https://api.slack.com/web
TOKEN = "<your_token>"

# output main directory, without final 'slash'
OUTPUTDIR = "output"

# enable debug?
DEBUG = False

### CONFIGURATION END ###

# constants

API = 'https://slack.com/api'

TIMESTAMPFILE = os.path.dirname(os.path.realpath(__file__))+"/offset.txt"

def response_to_json(response): return response.json

def set_timestamp(ts):
	try:
		out_file = open(TIMESTAMPFILE,"w")
		out_file.write(str(ts))
		out_file.close()
		return True
	except Exception, e:
		if DEBUG: print str(e)
		return False

def get_timestamp():
	try:
		in_file = open(TIMESTAMPFILE,"r")
		text = in_file.read()
		in_file.close()
		return int(text)
	except Exception, e:
		if DEBUG: print str(e)
		return None

def download_file(url, basedir, filename, date, user, channel):
	basedir += channel
	try:
		os.stat(basedir)
	except:
		os.mkdir(basedir)
	# converting date from epoch time to readable format
	date = time.strftime('%Y%m%d_%H%M%S', time.localtime(float(date)))
	filename, file_extension = os.path.splitext(filename)
	# retrieving full filename with path
	local_filename = basedir+'/'+str(date)+'-'+filename+'_by_'+user+file_extension
	print "Saving to", local_filename
	headers = {'Authorization': 'Bearer '+TOKEN}
	r = requests.get(url, headers=headers)
	with open(local_filename, 'wb') as f:
		for chunk in r.iter_content(chunk_size=1024):
			if chunk: f.write(chunk)
	return local_filename

def get_channel_name(id):
	url = API+'/channels.info'
	data = {'token': TOKEN, 'channel': id }
	response = requests.post(url, data=data)
	if DEBUG: pprint(response_to_json(response))
	return response_to_json(response)['channel']['name']

def get_user_name(id):
	url = API+'/users.info'
	data = {'token': TOKEN, 'user': id }
	response = requests.post(url, data=data)
	if DEBUG: pprint(response_to_json(response))
	return response_to_json(response)['user']['name']

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

if __name__ == '__main__':
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
		print('Found', fileCount, 'files')
		if fileCount == 0: break
		for f in json["files"]:
			try:
				if DEBUG: pprint(f)
				filename = str(f['name'])
				date = str(f['timestamp'])
				user = users.get(f['user'], get_user_name(f['user']))
				channel = get_channel_name(f['channels'][0])
				file_url = f["url_private_download"]
				print("Downloading file: '%s'" % file_url)
				download_file(file_url, OUTPUTDIR + '/', filename, date, user, channel);
				if ts == None or float(date) > float(ts): ts = date
			except Exception, e:
				if DEBUG: print str(e)
				pass
		page = page + 1
	if ts != None: set_timestamp(int(ts)+1)
	print('Finished.')