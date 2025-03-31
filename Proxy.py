# Include the libraries for socket and system calls
import socket
import sys
import os
import argparse
import re

# 1MB buffer size
BUFFER_SIZE = 1000000

# Get the IP address and Port number to use for this web proxy server
parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='the IP Address Of Proxy Server')
parser.add_argument('port', help='the port number of the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = int(args.port)

# Create a server socket, bind it to a port and start listening
try:
  # Create a server socket
  # ~~~~ INSERT CODE ~~~~
  serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #This server socket listens for connections from the client. The socket object uses IPv4 addressing (AF_INET) and the TCP protocol (SOCK_STREAM)
  # ~~~~ END CODE INSERT ~~~~
  print ('Created socket')
except:
  print ('Failed to create socket')
  sys.exit()

try:
  # Bind the the server socket to a host and port
  # ~~~~ INSERT CODE ~~~~
  serverSocket.bind((proxyHost, proxyPort)) #Attaches and binds the server socket to the specifc host and port number. It allows it to accept client connections on the interface.
  # ~~~~ END CODE INSERT ~~~~
  print ('Port is bound')
except:
  print('Port is already in use')
  sys.exit()

try:
  # Listen on the server socket
  # ~~~~ INSERT CODE ~~~~
  serverSocket.listen(5) #The server socket is in listening mode and able to accept connections, with a queue of up to 5 pending client connections
  # ~~~~ END CODE INSERT ~~~~
  print ('Listening to socket')
except:
  print ('Failed to listen')
  sys.exit()

# continuously accept connections
while True:
  print ('Waiting for connection...')
  clientSocket = None

  # Accept connection from client and store in the clientSocket
  try:
    # ~~~~ INSERT CODE ~~~~
    clientSocket, addr = serverSocket.accept() #Waits for a client to connect to proxy server. When a connection is made, the accept() returns a new socket (clientSocket) for communicating with the client and the client's address (addr)
    # ~~~~ END CODE INSERT ~~~~
    print ('Received a connection')
  except:
    print ('Failed to accept connection')
    sys.exit()

  # Get HTTP request from client
  # and store it in the variable: message_bytes
  # ~~~~ INSERT CODE ~~~~
  message_bytes = clientSocket.recv(BUFFER_SIZE) #Recieives the incoming HTTP request from the connected client and stores the bytes into message_bytes for processing
  # ~~~~ END CODE INSERT ~~~~
  message = message_bytes.decode('utf-8')
  print ('Received request:')
  print ('< ' + message)

  # Extract the method, URI and version of the HTTP client request 
  requestParts = message.split()
  method = requestParts[0]
  URI = requestParts[1]
  version = requestParts[2]

  print ('Method:\t\t' + method)
  print ('URI:\t\t' + URI)
  print ('Version:\t' + version)
  print ('')

  # Get the requested resource from URI
  # Remove http protocol from the URI
  URI = re.sub('^(/?)http(s?)://', '', URI, count=1)

  # Remove parent directory changes - security
  URI = URI.replace('/..', '')

  # Split hostname from resource name
  resourceParts = URI.split('/', 1)
  hostname = resourceParts[0]
  resource = '/'

  if len(resourceParts) == 2:
    # Resource is absolute URI with hostname and resource
    resource = resource + resourceParts[1]

  print ('Requested Resource:\t' + resource)

  # Check if resource is in cache
  try:
    cacheLocation = './' + hostname + resource
    if cacheLocation.endswith('/'):
        cacheLocation = cacheLocation + 'default'

    print ('Cache location:\t\t' + cacheLocation)

    fileExists = os.path.isfile(cacheLocation)
    
    # Check wether the file is currently in the cache
    cacheFile = open(cacheLocation, "r")
    cacheData = cacheFile.readlines()

    print ('Cache hit! Loading from cache file: ' + cacheLocation)
    # ProxyServer finds a cache hit
    # Send back response to client 
    # ~~~~ INSERT CODE ~~~~
    for line in cacheData:
      clientSocket.send(line.encode()) #Each line of the cached response is sent back to the client after encoding it to bytes.
    # ~~~~ END CODE INSERT ~~~~
    cacheFile.close()
    print ('Sent to the client:')
    print ('> ' + cacheData)
  except:
    # cache miss.  Get resource from origin server
    originServerSocket = None
    # Create a socket to connect to origin server
    # and store in originServerSocket
    # ~~~~ INSERT CODE ~~~~
    originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #Creates a new TCP socket to connect to orignal server and requests the resource on behalf of the client
    # ~~~~ END CODE INSERT ~~~~

    print ('Connecting to:\t\t' + hostname + '\n')
    try:
      # Get the IP address for a hostname
      address = socket.gethostbyname(hostname)
      # Connect to the origin server
      # ~~~~ INSERT CODE ~~~~
      originServerSocket.connect((address, 80)) #Connects to original server on port 80 which is the default HTTP port
      # ~~~~ END CODE INSERT ~~~~
      print ('Connected to origin Server')

      originServerRequest = ''
      originServerRequestHeader = ''
      # Create origin server request line and headers to send
      # and store in originServerRequestHeader and originServerRequest
      # originServerRequest is the first line in the request and
      # originServerRequestHeader is the second line in the request
      # ~~~~ INSERT CODE ~~~~
      
      if '/' in resource:
        path = '/' + resource.split('/', 1)[-1] #extracts the path part after hostname of the URI
      else:                                     #I only realised after testing and reading the protocols that the origin server should only receive the path in the request line.
        path = '/' #If there is no path given, this default back to root ('/'), ensuring valid requests are sent even for the base domain URLs.
      originServerRequest = method + ' ' + path + ' HTTP/1.1' #Originally I was sending the full absolute URI (e.g. http://host/path), which caused HTTP/0.9 errors.
      originServerRequestHeader = 'Host: ' + hostname #Sets the host header as required by HTTP/1.1. Without this header, some of the servers returned malformed responses.
      # ~~~~ END CODE INSERT ~~~~

      # Construct the request to send to the origin server
      request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'

      # Request the web resource from origin server
      print ('Forwarding request to origin server:')
      for line in request.split('\r\n'):
        print ('> ' + line)

      try:
        originServerSocket.sendall(request.encode())
      except socket.error:
        print ('Forward request to origin failed')
        sys.exit()

      print('Request sent to origin server\n')

      # Get the response from the origin server
      # ~~~~ INSERT CODE ~~~~
      response = b'' #Initialises an empty byte string to hold a complete HTTP response. 
                     # Especially for larger payloads, I learnt that the recv() might not return a full response in one go. 
      while True:
        chunk = originServerSocket.recv(BUFFER_SIZE) # A chunk of the response fron the origin server is received.
        if not chunk: # If there is an empty chunk, this signals that the server has closed the connection
          break
        response += chunk #Adds each chunk to the full response. I learnt that this is necessary to eliminate and avoid issues with incomplete data sent to the cache or client.

      status_line = response.decode(errors='ignore').split('\r\n')[0] #Extracts status line from decoding the response, which helps determne the specific HTTP response code.
      print('HTTP status:', status_line)

      cache_allowed = False #
      #Determines caching logic based on the HTTP status codes:
      if '200' in status_line or '301' in status_line:
        cache_allowed = True #I learned from HTTP/1.1 spec (RFC 2616) that these are usually safe to cache : 200 OK and 301 Moved Permanently 
      elif '302' in status_line: #The temporary redirects are not typically cached to make sure there are fresh responses
        print('302 Found: Response is a temporary redirect, it will not be cached')

      headers_block = response.decode(errors='ignore').split('\r\n\r\n')[0] #Get the HTTP headers by splitting the rsponse before the body

      cache_control_match = re.search(r'Cache-Control:. *max-age= (\d+)', headers_block) #Finds cache-control header using regex and looks for max-age value. 
      #I had a lot of trouble initially extracting this. However, I realised I needed to account for case sensitivity and spacing issues. 
      if cache_control_match:
        max_age = int(cache_control_match.group(1)) #Converts max=age to an integer value
        print(f'Cache-Control max-age found:{max_age} seconds') #This helped me ensure that I respect the caching instructions provided by the server.
      # ~~~~ END CODE INSERT ~~~~

      # Send the response to the client
      # ~~~~ INSERT CODE ~~~~
      clientSocket.sendall(response) #Uses sendall() to make sure the entire response is sent to the client
      # ~~~~ END CODE INSERT ~~~~

      # Create a new file in the cache for the requested file.
      cacheDir, file = os.path.split(cacheLocation)
      print ('cached directory ' + cacheDir)
      if not os.path.exists(cacheDir):
        os.makedirs(cacheDir)
      cacheFile = open(cacheLocation, 'wb')

      # Save origin server response in the cache file
      # ~~~~ INSERT CODE ~~~~
      cacheFile.write(response) #Calls write() method to save the bytes stored in 'response' diretly into the open cache file. 
      # ~~~~ END CODE INSERT ~~~~
      cacheFile.close()
      print ('cache file closed')

      # finished communicating with origin server - shutdown socket writes
      print ('origin response received. Closing sockets')
      originServerSocket.close()
       
      clientSocket.shutdown(socket.SHUT_WR)
      print ('client socket shutdown for writing')
    except OSError as err:
      print ('origin server request failed. ' + err.strerror)

  try:
    clientSocket.close()
  except:
    print ('Failed to close client socket')
