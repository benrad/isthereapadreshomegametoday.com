# isthereapadreshomegametoday.com
Is there a Padres home game today? It'll tell you with a bit (not much) of wit.

If you want a Slack notification, it can do that, too.

I run the Flask app on an AWS t2.micro instance with Apache. The notifier is simply run at 9 am and 5 pm by a cron job. 
CSV schedules can be downloaded from [city].[team name].mlb.com/schedule/downloadable.jsp?c_id=[team id]
