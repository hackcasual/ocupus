#!/usr/bin/python

import requests
import Queue
import threading
import urllib
import urllib2

class Message:
	def __init__(self, type, data):
		self.type = type
		self.data = data

	def __repr__(self):
		return str(self.type) + ":" + self.data

def hanging_get(my_id, messages):
	while True:
		r = requests.get('http://localhost:8888/wait?peer_id=' + str(my_id))
		if r.status_code == 200:		

			print r.text

			if int(r.headers['pragma']) == my_id:
				messages.put(Message(0, r.text))
			else:
				messages.put(Message(int(r.headers['pragma']), r.text))

def send_message(my_id, peer_id, message):
	print "Making request"

	data = message
	req = urllib2.Request("http://localhost:8888/message?peer_id=" + str(my_id) + "&to=" + str(peer_id), data)
	response = urllib2.urlopen(req)
	the_page = response.read()

	print the_page

r = requests.get('http://localhost:8888/sign_in?ocupus_orchestrator')

peers = dict()

connected = r.text.split("\n")

my_info = connected[0].split(",")
my_id = int(my_info[1])

messages = Queue.Queue()

for l in connected[1:]:
	info = l.split(",")
	if len(info) > 1:
		print info
		peers[info[0]] = int(info[1])

t = threading.Thread(target=hanging_get, args = (my_id, messages))
t.daemon = True
t.start()

while True:
	if not messages.empty():
		print messages.get()
		send_message(my_id, peers["receiver"], "Howdy!")