from flask import Flask, redirect, request, render_template, Response, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from datetime import date, timedelta
from requests import get
from uuid import uuid4
import json
import random
import csv


app = Flask(__name__)
app.config.from_object('config')
db = SQLAlchemy(app)


class SlackException(Exception):
	pass


class User(db.Model):
	user_id = db.Column(db.String(36), primary_key=True)
	hook_url = db.Column(db.Text, unique=True)
	channel_id = db.Column(db.Text, unique=True)
	channel_name = db.Column(db.Text)
	today = db.Column(db.Boolean)
	tomorrow = db.Column(db.Boolean)
	
	access_token = db.Column(db.Text)
	team_name = db.Column(db.Text)
	team_id = db.Column(db.Text)
	configuration_url = db.Column(db.Text)

	def __init__(self, oauth_response):
		hook = oauth_response['incoming_webhook']
		self.user_id = str(uuid4())
		self.hook_url = hook['url']
		self.channel_id = hook['channel_id']
		self.channel_name = hook['channel']
		# Intialized as True, False because user doesn't set these until after user is created
		# Today is true because someone might close the page before finishing
		self.today = True
		self.tomorrow = False
		self.access_token = oauth_response['access_token']
		self.team_name = oauth_response['team_name']
		self.team_id = oauth_response['team_id']
		self.configuration_url = hook['configuration_url']

	def set_notification_time(self, today, tomorrow):
		self.today = today
		self.tomorrow = tomorrow

	def __repr__(self):
		return '<User {0}>'.format(self.user_id)


def check_schedule():
	today = date.today().strftime('%-m/%-d/%y')
	with open('/var/www/padres/schedule.csv', 'rU') as f:
		reader = csv.reader(f)
		for row in reader:
			if today == row[0]: # Today's the day.
				try:
					if int(row[1][0]) < 5: # Earlier than 5PM start.
						return True, True # There's a game and it's a day game.
				except ValueError:
					return False, False #C 'mon, this is an evening project.
				return True, False	# There's a game but it's not a day game.
	return False, False # There's no game at all. God this logic is fast but gross.


def get_game_time(target):
	with open('/var/www/padres/schedule.csv', 'rU') as f:
		reader = csv.reader(f)
		for row in reader:
			if row[0] == target:
				return json.dumps({'game': True, 'time': row[1]})
		return json.dumps({'game': False, 'time': None})


def oauth_access(code, request_base):
	url = "https://slack.com/api/oauth.access?client_id={0}&client_secret={1}&code={2}&redirect_uri={3}".format(
		app.config['CLIENT_ID'], app.config['CLIENT_SECRET'], code, request_base)
	resp = get(url)
	if resp.status_code == 200:
		content = json.loads(resp.content)
		if content['ok']:
			return content
		else:
			raise SlackException('Bad OAuth Request: {0}'.format(content['error']))
	else:
		raise SlackException('Bad OAuth Response: {0}'.format(resp.content))


@app.route('/')
def index():
	positive = random.choice(["It's smooth sailing all the way home.", 
				"May the emptiness be the wind beneath your wings.",
				"Aw yiss."])
	negative = random.choice(["Well, shit.",
				"At least their record isnt' as terrible as the traffic.",
				"Hope that car seat's comfy.",
				"There go your evening plans."])
	day = random.choice(["Better eat those leftovers you've been saving.",
			"Don't even think about trying to get Subway.",
			"Looks like it's lunch at your desk."])

	playing, isDayGame = check_schedule()

	if playing:
		if isDayGame:
			phrase = day
		else:
			phrase = negative
	else:
		phrase = positive

	playing = "Yes." if playing else "No."

	dayGame = "And even worse, it's a day game." if isDayGame else " "

	return render_template('index.html', areTheyPlaying=playing, day=dayGame, wittyPhrase=phrase)


@app.route('/slack/', methods=['GET'])
def slack_create():
	state = str(uuid4())
	session['state'] = state
	return render_template('slack.html', state = state)


@app.route('/slackconfirm/', methods=['GET'])
def slack_confirm_get():
	if 'state' not in request.args or 'code' not in request.args:
		return 'Whoops, there was a problem setting up the integration. Please try again later.\nError code: 0d06103d', 400
	if request.args.get('state') != session['state']:
		return 'Whoops, there was a problem setting up the integration. Please try again later.\nError code: d08fa1f2', 400
	try:
		oauth_response = oauth_access(request.args.get('code'), request.base_url)
	except SlackException:
		return 'Whoops, there was a problem setting up the integration. Please try again later.\nError code: 6703621f', 400
		# TODO: logging
	
	user = User(oauth_response)
	db.session.add(user)
	try:
		db.session.commit()
	except IntegrityError:
		return "Whoops, it looks like you've already set up an integration for this channel!"
	session['uid'] = user.user_id
	return render_template('slackconfirm.html')


@app.route('/slackconfirm/', methods=['POST'])
def slack_confirm_post():
	if 'uid' not in session:
		return 'Whoops, there was a problem setting up the integration. Please try again later.\nError code: 8bb10d99', 400
	uid = session['uid']
	user = User.query.filter_by(user_id=uid).first()
	if not user:
		return 'Whoops, there was a problem setting up the integration. Please try again later.\nError code: 23b11192', 400
	notify_time = request.form['notify_time']
	today = True if notify_time == 'today' or notify_time == 'both' else False
	tomorrow = True if notify_time == 'tomorrow' or notify_time == 'both' else False
	user.set_notification_time(today, tomorrow)
	db.session.commit()
	if today and tomorrow:
		time = "5 pm the day before a game and 9 am the day of."
	elif today:
		time = "9 am on game day."
	else:
		time = "5 pm the day before game day." 
	return render_template('success.html', time=time)


@app.route('/slackdelete/')
def delete_user():
	return "oh shit, this isn't implemented yet", 500


@app.route('/notifycheck/')
def notifycheck():
	if request.args.has_key('day'):
		day = request.args.get('day')
		if day != 'today' and day != 'tomorrow':
			return 'Bad day parameter', 400
		delta = 1 if day == 'tomorrow' else 0
		target = (date.today() + timedelta(days=delta)).strftime('%-m/%-d/%y')
		return get_game_time(target)
	else:
		return 'No day provided', 400


# if __name__ == '__main__':
# 	app.run()
