from requests import get, post
from sys import argv
from application import User
import json


bad_response = {'game': False, 'time': None}


def check_schedule(day):
	response = get('http://isthereapadreshomegametoday.com/notifycheck/?day={0}'.format(day))
	if response.status_code == 200:
		content = json.loads(response.content)
		return content
	return bad_response


def send_notification(user, day, time):
	channel_id = user.channel_id
	url = user.hook_url
	message = "There's a Padres home game {0} at {1}.".format(day, time)  # <http://isthereapadreshomegametoday.com/slackdelete?{2}|(stop notifications)>".format(day, time, channel_id)
	headers = {'Content-type': 'application/json'}
	data = json.dumps({'text': message})
	return post(url, data=data, headers=headers)


def check_and_notify(day):
	"""
	param day: today or tomorrow. "today" notifications at 9 am, "tomorrow" at 5 pm
	"""
	game_data = check_schedule(day)

	if not game_data['game']:
		print "No game; no notifications sent"
		return
	time = game_data['time']
	if day == 'today':
		users = User.query.filter_by(today=True).all()
	elif day == 'tomorrow':
		users = User.query.filter_by(tomorrow=True).all()
	if users:
		for user in users:
			send_notification(user, day, time)
	print "Game {0} at {1}; notified {2}".format(day, time, users)
	return

if __name__ == '__main__':
	check_and_notify(argv[1])
