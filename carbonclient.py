#!/usr/bin/env python
"""
Simple python code that allows a connection to a carbon-cache sever for graphite.
This can be used as a python library or a standalone executeable.

from the command line...

	./carbonclient.py -m filesystem._root -v 53
	./carbonclient.py -c cabonserver.example.com -p 2003 -g prodcution -s myservername -m df_root -v 53
	./carbonclient.py -c cabonserver.example.com -p 2003 -g prodcution -s myservername -m df_root -v $( df -k / | awk '{print $5}' | sed 's/[^0-9]//g' | tail -1 )

from python

	>>> from carbonclient import update
	>>> update(metric="filesystem._root", value=53)
	>>> update(server="cabonserver.example.com", port=2003, group="production", metric="filesystem._root", value=53)
	>>> update(server="cabonserver.example.com", port=2003, group="production", metric="filesystem._root", value=get_df('/'))

Written by Daniel Lawrence <daniel@danielscottlawrence.com>
	
"""

#------------------------------------------------------------------------------
import sys
import time
import socket
#------------------------------------------------------------------------------
class ConnectionError(Exception): 
	def __init__(self, value=None):
		self.value = value
	def __str__(self):
		return repr(self.value)

class MissingValue(): 
	def __init__(self, value=None):
		self.value = value
	def __str__(self):
		return repr(self.value)


		
#------------------------------------------------------------------------------
class Carbon(object):
	""" The object that will handle the communication and formatting to the carbon server """

	#------------------------------------------------------------------------------
	def __init__(self, server='127.0.0.1',port=2003):
		self.server = server
		self.port = port
		self.message = []
		self.connection_timeout = 1
		self.socket = socket.socket()
		# Holding flags
		self.debug = False
		self.connected = False

	#------------------------------------------------------------------------------
	def Debug( self, message=None ):
		""" Generic debug message, print a message if self.debug=True """
		if self.debug:
			print "DEBUG: %s" % message.strip()

	#------------------------------------------------------------------------------
	def connect(self):
		""" Make a connection to the carbon server to make sure we can send it data """
		try:
			self.Debug( "connecting to %s:%s with a %s second timeout" % ( self.server, self.port, self.connection_timeout ))
  			self.socket.settimeout(self.connection_timeout)	# set timeout to 1 second
  			self.socket.connect( (self.server,self.port) )	# connect to the carbonserver
			self.Debug( "connected to %s:%s" % ( self.server, self.port) )
		except socket.error:
  			raise ConnectionError( "Connect failed to %(server)s:%(port)d, is carbon-agent.py running?" % { 'server':self.server, 'port':self.port } )
		# update the connection status with True ( True is connected )
		self.connected = True


	#------------------------------------------------------------------------------
	def disconnect(self):
		""" close the socket connection to the carbon server """
		if self.connected:
			# if we are going to disconnect make sure the messages are empty
			if self.message:
				self.submit()
			self.socket.shutdown(1)
			self.Debug( "disconnected from %s:%s" % ( self.server, self.port) )
			self.connected = False
		else:
			self.Debug( "Not connected to %s:%s" % ( self.server, self.port) )

	#------------------------------------------------------------------------------
	def send(self, message=None):
		""" send the string to the carbon server, and watch for known errors """
		try:
			self.Debug( "sending message to %s:%d" % ( self.server, self.port ) )
  			self.socket.sendall(message)
		except socket.error:
			raise ConnectionError( "failed to send message to %s:%d" % ( self.server, self.port ) )
		except AttributeError:
			raise ConnectionError( "socket is not configured as expected, have you Carbon.connect()'ed?" )
		
	#------------------------------------------------------------------------------
	def submit(self, message=None):
		""" 
		If the message/submit are a list, thenn collapse it into a string 
		then send that string to the carbon server using Carbon.send(message)
		"""
		# If submit has been called without a message, then use the stored message in the object
		if not message:
			message = self.message
			self.message = []

		# Check if we are connected to the carbonserver, if we are not connected, then connect...
		if not self.connected:
			self.connect()

		# Update with the data string that will be sent to the carbon server
		# * all lines must start with a new line
		# * all lines must end with a new line
		if type(message) == type([]):
  			message = '\n'.join(message) + '\n'
		#if not message.startswith('\n'):
  		#	message = '\n' + message
		#if not message.endswith('\n'):
  		#	message = message + '\n'

		message = message.lower()

		self.Debug("Updating carbon-cache with '%s'" % message.strip())

		self.send(message)

	#-----------------------------------------------------------------------------------------------------------------------------------------------------
	def append(self,group=None,server=None,metric=None,value=None, epoch=None):
		""" Creates Cabon object and sends the updates to the carbon server """

		# make sure we have a value
		if value == None:
			raise MissingValue("Value is required")

		# rename localhost to the real server name
		if server == "localhost" or not server:
			# grab the uname from the system
			from os import uname
			# overwrite localhost with real name
			server = uname()[1]

		# remote FQDN from the servername as long as it isn't an IP
                if server[0].isdigit():
                    server = server.split('.')[0]

		# if group is the default the take the first letter from the host, to keep the list short
		if not group:
			group = "systems.%s" % server[0]
			self.Debug("using the default group of %s" % group )

                try:
                    float(value)
                except TypeError:
                    sys.stderr.write("Stop being a doofus with something like %s\n" % value)

                if not epoch:
                    epoch=time.time()
                else:
                    epoch=int(epoch)

		# convert our data into a string that the carbon server will read.
		message = "%s.%s.%s %f %d" % ( group, server, metric, float(value), epoch)

		# update the message 
		self.message.append(message)

#-----------------------------------------------------------------------------------------------------------------------------------------------------
def main(options,args):
	""" Invoked when running this tool directly, not as a library """
	# IF we dont any any custom agruments then we assume is a test.
	update(	carbonserver=options.carbonserver, carbonport=int(options.port), group=options.group, server=options.server, 
		metric=options.metric, value=options.value, debug=options.debug, epoch=options.epoch)
	sys.exit(0)

#-----------------------------------------------------------------------------------------------------------------------------------------------------
def bulk_update(carbonserver="carbon",carbonport=2003,group=None,server=None,metric_value=None,debug=False):
	""" Creates Cabon object and sends the updates to the carbon server """

	carbon = Carbon(server=carbonserver, port=carbonport) 			# Make a Carbon object, so we can connect/update/send/disconnect
	carbon.debug = debug							# Set debug mode if required
	for mv in metric_value:
		carbon.append(group=group,server=server,metric=mv['metric'],value=mv['value'])	# Convert the kv* to string to updates
	carbon.submit()								# send updates to remote carbon-cache
	carbon.disconnect()							# disconnect from carbon
		

#-----------------------------------------------------------------------------------------------------------------------------------------------------
def update(carbonserver="carbon",carbonport=2003,group=None,server=None,metric=None,value=None,debug=False, epoch=None):
	""" Creates Cabon object and sends the updates to the carbon server """

	carbon = Carbon(server=carbonserver, port=carbonport)	# Make a Carbon object, so we can connect/update/send/disconnect
	carbon.debug = debug
	carbon.append(group=group,server=server,metric=metric,value=value, epoch=epoch)	# Convert the kv* to string to updates
	carbon.submit()						# send updates to remote carbon-cache
	carbon.disconnect()					# disconnect from carbon

#-----------------------------------------------------------------------------------------------------------------------------------------------------
# Main:
#-----------------------------------------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
	from optparse import OptionParser
	usage = "%s [-d] [-c carbonserver] [-p carbonserver_port ] [ -g group ] [ -s server ] -m metric -v value\n\nDefault server:\tcarbon:2003\nDefault group:\tsystems" % sys.argv[0]
	parser = OptionParser(usage)
	# Carbon server details
	parser.add_option("-c", "--carbonserver", dest="carbonserver", default='carbon', help="server running carbon server", metavar="carbonserver")
	parser.add_option("-p", "--port", dest="port", default=2003, help="port listen on the deserverrunning carbon server", metavar="port")
	# metrics
	parser.add_option("-g", "--group", dest="group", default=None, help="use this to collect a group servers together", metavar="group")
	parser.add_option("-s", "--server", dest="server", default='localhost', help="name of the server/service the metric will be collect for", metavar="server")
	parser.add_option("-m", "--metric", dest="metric", default=None, help="Name of the metric that the value will be stored with", metavar="metric")
	parser.add_option("-v", "--value", dest="value", default=None, help="The value of the metric that will stored", metavar="value")
	parser.add_option("-t", "--time", dest="epoch", default=None, help="The time of the datapoint that will stored in epoch", metavar="epoch")
	# debug
	parser.add_option("-d", "--debug", action="store_true", dest="debug", default=False, help="Turn on debug mode", metavar="debug")

	(options, args) = parser.parse_args()

	print options, args

	if not options.metric:
		print parser.get_usage()
		print "missing the name of the metric, -m METRIC_NAME."
		print "example: %s -m random_int -v 24" % sys.argv[0]
		sys.exit(2)
	if not options.value:
		print parser.get_usage()
		print "missing the value of for %s -v VALUE" % ( options.metric )
		print "example: %s -m random_int -v 24" % sys.argv[0]
		sys.exit(3)

	main(options,args)
#-----------------------------------------------------------------------------------------------------------------------------------------------------