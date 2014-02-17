#!/usr/bin/python

import requests
import Queue
import threading

class Message:
	def __init__(self, type, data):
		self.type = type
		self.data = data

	def __repr__(self):
		return str(self.type) + ":" + self.data

def hanging_get(my_id, messages):
	while True:
		r = requests.get('http://192.168.1.182:8888/wait?peer_id=' + str(my_id))
		if r.status_code == 200:		

			print r.text

			if int(r.headers['pragma']) == my_id:
				messages.put(Message(0, r.text))
			else:
				messages.put(Message(int(r.headers['pragma']), r.text))

r = requests.get('http://192.168.1.182:8888/sign_in?ocupus_orchestrator')

peers = dict()

connected = r.text.split("\n")

my_info = connected[0].split(",")
my_id = int(my_info[1])

messages = Queue.Queue()

for l in connected[1:]:
	info = l.split(",")
	if len(info) > 1:
		print info
		peers[int(info[1])] = info[0]

t = threading.Thread(target=hanging_get, args = (my_id, messages))
t.daemon = True
t.start()

print messages.get()