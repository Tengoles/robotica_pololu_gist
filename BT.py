# Uses Bluez for Linux
#
# sudo apt-get install bluez python-bluez
# 
# Taken from: https://people.csail.mit.edu/albert/bluez-intro/x232.html
# Taken from: https://people.csail.mit.edu/albert/bluez-intro/c212.html

import bluetooth, subprocess
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
  sock.send("hello!!")
  sock.close()
  
def lookUpNearbyBluetoothDevices():
  nearby_devices = bluetooth.discover_devices()
  for bdaddr in nearby_devices:
    print str(bluetooth.lookup_name( bdaddr )) + " [" + str(bdaddr) + "]"
    
    
if __name__ == "__main__":
    #nearby_devices = bluetooth.discover_devices()
    #for bdaddr in nearby_devices:
    #	print str(bluetooth.lookup_name( bdaddr )) + " [" + str(bdaddr) + "]"
    addr = "20:15:11:02:89:17"      # Device Address
    port = 1         # RFCOMM port
    # Now, connect in the same way as always with PyBlueZ
    try:
        s = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        s.connect((addr,port))
        #s.send('C')
        s.send('W')
        s.send('C')
        sleep(3)
        s.send('S')
        sleep(1)
        s.send('W')
        s.send('C')
        sleep(1)
        s.send('S')
        s.close()
    except bluetooth.btcommon.BluetoothError as err:
        print(err)
        # Error handler
        pass

