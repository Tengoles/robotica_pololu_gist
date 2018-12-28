# Uses Bluez for Linux
#
# sudo apt-get install bluez python-bluez
# 
# Taken from: https://people.csail.mit.edu/albert/bluez-intro/x232.html
# Taken from: https://people.csail.mit.edu/albert/bluez-intro/c212.html

import bluetooth
import time
from time import sleep

def receiveMessages():
  server_sock=bluetooth.BluetoothSocket( bluetooth.RFCOMM )
  
  port = 1
  server_sock.bind(("",port))
  server_sock.listen(1)
  
  client_sock,address = server_sock.accept()
  print "Accepted connection from " + str(address)
  
  data = client_sock.recv(1024)
  print "received [%s]" % data
  
  client_sock.close()
  server_sock.close()
  
def sendMessageTo(targetBluetoothMacAddress):
  port = 1
  sock=bluetooth.BluetoothSocket( bluetooth.RFCOMM )
  sock.connect((targetBluetoothMacAddress, port))
  #sock.send("Z  \n")
  sock.send("Z")
  sock.send('\x18')
  sock.send('\x18')
  sock.send('\n')
  sock.close()
  
def lookUpNearbyBluetoothDevices():
  nearby_devices = bluetooth.discover_devices()
  for bdaddr in nearby_devices:
    print (str(bluetooth.lookup_name( bdaddr )) + " [" + str(bdaddr) + "]")
    
    
if __name__ == "__main__":
    #nearby_devices = bluetooth.discover_devices()
    #for bdaddr in nearby_devices:
    #	print str(bluetooth.lookup_name( bdaddr )) + " [" + str(bdaddr) + "]"
    addr = "20:15:11:02:89:17"      # Device Address
    port = 1         # RFCOMM port
    # Now, connect in the same way as always with PyBlueZ
    try:
        sendMessageTo(addr)
        time.sleep(0.01)
        #receiveMessages()
        """print('envie')
        server_socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        server_socket.bind(("", 3))
        server_socket.listen(1)

        client_socket, address = server_socket.accept()

        data = client_socket.recv(1024)

        print
        "received [%s]" % data

        server_socket.close()"""
        """s = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        s.bind((addr,port))
        s.connect((addr,port))
        sleep(1)
        #s.send('C')
        s.send(str(chr(0xA5)))
        s.send(' ')
        s.send(' ')
        s.send('\n')
        #s.close()"""
    except bluetooth.btcommon.BluetoothError as err:
        print(err)
        # Error handler
        pass

