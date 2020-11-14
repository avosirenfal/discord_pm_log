from collections import defaultdict
from tzlocal import get_localzone
from datetime import datetime
from unidecode import unidecode
import json, requests, os, codecs, time, errno, signal, string, re

# timezone goes here
tz_out = get_localzone() #tz.gettz('America/New_York')

# username, user token
users = [
	('some_username', 'users_token'),
]

# relative path if None, else absolute path
write_path = None # /somewhere/directory




invalid_fn_reg = re.compile('[^%s]+' % (re.escape(''.join(frozenset("-_.() %s%s" % (string.ascii_letters, string.digits))))))
underscore_reg = re.compile('_+')

def sanitize_filename(fn):
	ret = invalid_fn_reg.sub('_', fn)
	ret = underscore_reg.sub('_', ret)
	if(ret == '_'):
		return None
	return ret


def mkdir_tree(path):
	try:
		os.makedirs(path)
	except OSError as ex:
		if(ex.errno == errno.EEXIST and os.path.isdir(path)):
			return
		else:
			raise ex

class CatchKeyboardInterrupt(object):
	def __enter__(self):
		self.signal_received = False
		# block normal SIGINT handler
		self.old_handler = signal.getsignal(signal.SIGINT)
		signal.signal(signal.SIGINT, self.handler)

	def handler(self, sig, frame):
		self.signal_received = True

	def __exit__(self, type, value, traceback):
		# set SIGNIT handler back to normal
		signal.signal(signal.SIGINT, self.old_handler)

def req(uri, token, params=None):
	while True:
		req = requests.request('GET', r'https://discordapp.com/api/%s' % (uri,), headers={'Authorization': token}, params=params)
		#print(req.url)
		ret = json.loads(req.text)

		if('retry_after' in ret):
			retry = (int(ret['retry_after']) + 750) / 1000.0
			print('[-] Rate limit exceeded, retrying in %.2f seconds' % (retry))
			time.sleep(retry)
			continue

		if(req.status_code != 200):
			raise Exception('Status code %s from Discord API: %r' % (req.status_code, req.text))

		return ret

hit_usernames = dict()

def pull(username, token):
	# savepoints stores the last message ID we've pulled from the server on previous runs
	savepoints = defaultdict(lambda: 0)

	if(write_path):
		base_outpath = os.path.join(write_path, username)
	else:
		base_outpath = os.path.join(username)

	mkdir_tree(base_outpath)


	savepoint_fn = os.path.join(base_outpath, 'savepoint.json')

	if(os.path.exists(savepoint_fn)):
		try:
			with open(savepoint_fn, 'rb') as f:
				for k,v in json.loads(f.read()).items():
					savepoints[int(k)] = int(v)
		except:
			print('[!] Failed loading savepoint information')
			raise

	print('[*] Pulling direct messages for %s' % (username,))
	dms = req('users/@me/channels', token)

	for conv in dms:
		if(conv['type'] != 1):
			print('[-] Skipping group chat with ID: %s' % (conv['id']))
			continue

		recipient = conv['recipients'][0]
		# prepare write directory
		dmusername = unidecode(recipient['username']).lower()
		outname = sanitize_filename(dmusername)
		uid = int(recipient['id'])

		if(outname in hit_usernames):
			print('[!] Username collision, two usernames both would write to output directory: %r [user1: %r, user2: %r]' % (outname,hit_usernames[outname],dmusername))
			break

		hit_usernames[outname] = dmusername

		outpath = os.path.join(base_outpath, outname)
		mkdir_tree(outpath)

		last_msg = None

		print('[*] Pulling conversations with %s (%s)' % (outname, uid))

		while True:
			# pull the next set of messages (100 at a time) starting at either 0, or the last message we saved from a previous run
			convd = req('channels/%s/messages' % (conv['id'],), token, {'after': savepoints[uid]})

			if(len(convd) < 1):
				break

			# buffer all writes to memory first in case user presses control+c and breaks program mid-write
			# we don't want savepoints being desynchronized from the actual state of the log files
			write_block = []
			last_fn = None
			last = None

			# parse UTC timestamps into local time datetime objects, create posix timestamps for sorting
			for msg in convd:
				dt = datetime.fromisoformat(msg['timestamp'])
				msg['timestamp'] = dt.astimezone(tz_out)
				msg['posix'] = int(dt.timestamp())

			# Discord API doesn't return messages in order, sort them now
			convd = sorted(convd, key=lambda x: x['posix'])

			for msg in convd:
				fn = msg['timestamp'].strftime('%m-%d-%Y.log')

				# determine what log file this message belongs in
				if(fn != last_fn):
					last_fn = fn
					last = []
					write_block.append((os.path.join(outpath, fn), last))

				last.append('[%s]%s %s: %s' % (
					msg['timestamp'].strftime('%I:%M %p').upper(),
					'*' if msg['edited_timestamp'] != None else '',
					msg['author']['username'],
					msg['content'],
				))

			# the write itself can't be interrupted
			catch_ki = CatchKeyboardInterrupt()

			with catch_ki:
				last_id = int(convd[-1]['id'])
				savepoints[uid] = last_id

				for fn, msgs in write_block:
					# only show a writing message when we first start writing a new date
					if(last_msg != fn):
						print('[*] Writing %s' % (fn,))
						last_msg = fn

					with codecs.open(fn, 'a', 'UTF-8') as f:
						f.write('%s\n' % ('\n'.join(msgs),))

				with codecs.open(savepoint_fn, 'w', 'UTF-8') as f:
					f.write(json.dumps(savepoints))

			# if the user interrupted us during write, exit now that we're done saving
			if(catch_ki.signal_received):
				return False

def main():
	for user, token in users:
		if(pull(user, token) == False):
			return

if(__name__ == '__main__'):
	main()
