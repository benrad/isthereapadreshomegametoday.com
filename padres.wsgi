import logging, sys
sys.path.insert(0, '/var/www/padres')
logging.basicConfig(stream=sys.stderr)

from application import app as application
