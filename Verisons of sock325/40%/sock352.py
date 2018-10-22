# sock352.py 

# (C) 2018 by R. P. Martin, under the GPL license, version 2.

# this is the skeleton code that defines the methods for the sock352 socket library, 
# which implements a reliable, ordered packet stream using go-back-N.
#
# Note that simultaneous close() is required, does not support half-open connections ---
# that is outstanding data if one side closes a connection and continues to send data,
# or if one side does not close a connection the protocol will fail.

from inspect import currentframe, getframeinfo

import socket as ip
import random
import binascii
import threading
import time
import sys
import struct as st
import os
import signal
import random

# The first byte of every packet must have this value
MESSAGE_TYPE = 0x44

# this defines the sock352 packet format.
# ! = big endian, b = byte, L = long, H = half word
HEADER_FMT = '!bbLLH'

# this are the flags for the packet header 
SYN =  0x01    # synchronize 
ACK =  0x02    # ACK is valid 
DATA = 0x04    # Data is valid 
FIN =  0x08    # FIN = remote side called close 

# max size of the data payload is 63 KB
MAX_SIZE = (63*1024)

# max size of the packet with the headers 
MAX_PKT = ((16+16+16)+(MAX_SIZE))

# these are the socket states 
STATE_INIT = 1
STATE_SYNSENT = 2
STATE_LISTEN  = 3
STATE_SYNRECV = 4 
STATE_ESTABLISHED = 5
STATE_CLOSING =  6
STATE_CLOSED =   7
STATE_REMOTE_CLOSED = 8


# function to print. Higher debug levels are more detail
# highly recommended 
def dbg_print(level,string):
    global sock352_dbg_level 
    if (sock352_dbg_level >=  level):
        print string 
    return 

# this is the thread object that re-transmits the packets 
class sock352Thread (threading.Thread):
    
    def __init__(self, threadID, name, delay):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.delay = float(delay)
        
    def run(self):
        dbg_print(3,("sock352: timeout thread starting %s delay %.3f " % (self.name,self.delay)) )
        scan_for_timeouts(self.delay)
        dbg_print(3,("sock352: timeout thread %s Exiting " % (self.name)))
        return 
      
# Example timeout thread function
# every <delay> seconds it wakes up and re-transmits packets that
# have been sent, but not received. A received packet with a matching ack
# is removed from the list of outstanding packets.

def scan_for_timeouts(delay):
    global list_of_outstanding_packets
    list_of_outstanding_packets = {}

    time.sleep(delay)

    # there is a global socket list, although only 1 socket is supported for now 
    while ( True ):

        time.sleep(delay)
        # example 
        for packet in list_of_outstanding_packets: 

            current_time = time.time()
            time_diff = float(current_time) - float(packet.time_sent)
                
            dbg_print(5,"sock352: packet timeout diff %.3f %f %f " % (time_diff,current_time,skbuf.time_sent))
            if (time_diff > delay):
                    dbg_print(3,"sock352: packet timeout, retransmitting")
                    # your transmit code here ... 
        
    return 


# This class holds the data of a packet gets sent over the channel 
# 
class Packet:
    def __init__(self):
        self.type = MESSAGE_TYPE    # ID of sock352 packet
        self.cntl = 0               # control bits/flags 
        self.seq = 0                # sequence number 
        self.ack = 0                # acknowledgement number 
        self.size = 0               # size of the data payload 
        self.data = b''             # data 

    # unpack a binary byte array into the Python fields of the packet 
    def unpack(self,bytes):
        # check that the data length is at least the size of a packet header 
        data_len = (len(bytes) - st.calcsize('!bbLLH'))
        if (data_len >= 0):

            new_format = HEADER_FMT + str(data_len) + 's'
            values = st.unpack(new_format,bytes)
            self.type = values[0]
            self.cntl = values[1]
            self.seq  = values[2]
            self.ack  = values[3]
            self.size = values[4] 
            self.data = values[5]
            # you dont have to have to implement the the dbg_print function, but its highly recommended 
            dbg_print (1,("sock352: unpacked:0x%x cntl:0x%x seq:0x%x ack:0x%x size:0x%x data:x%s" % (self.type,self.cntl,self.seq,self.ack,self.size,binascii.hexlify(self.data))))
        else:
            dbg_print (2,("sock352 error: bytes to packet unpacker are too short len %d %d " % (len(bytes), st.calcsize('!bbLLH'))))

        return
    
    # returns a byte array from the Python fields in a packet 
    def pack(self):
        if (self.data == None): 
            data_len = 0
        else:
            data_len = len(self.data)
        if (data_len == 0):
            bytes = st.pack('!bbLLH',self.type,self.cntl,self.seq,self.ack,self.size)
        else:
            new_format = HEADER_FMT + str(data_len) + 's'  # create a new string '!bbLLH30s' 
            dbg_print(5,("cs352 pack: %d %d %d %d %d %s " % (self.type,self.cntl,self.seq,self.ack,self.size,self.data)))
            bytes = st.pack(new_format,self.type,self.cntl,self.seq,self.ack,self.size,self.data)
        return bytes
    
    # this converts the fields in the packet into hexadecimal numbers 
    def toHexFields(self):
        if (self.data == None):
            retstr=  ("type:x%x cntl:x%x seq:x%x ack:x%x sizex:%x" % (self.type,self.cntl,self.seq,self.ack,self.size))
        else:
            retstr= ("type:x%x cntl:x%x seq:x%x ack:x%x size:x%x data:x%s" % (self.type,self.cntl,self.seq,self.ack,self.size,binascii.hexlify(self.data)))
        return retstr

    # this converts the whole packet into a single hexidecimal byte string (one hex digit per byte)
    def toHex(self):
        if (self.data == None):
            retstr=  ("%x%x%x%xx%x" % (self.type,self.cntl,self.seq,self.ack,self.size))
        else:
            retstr= ("%x%x%x%x%xx%s" % (self.type,self.cntl,self.seq,self.ack,self.size,binascii.hexlify(self.data)))
        return retstr


# the main socket class
# you must fill in all the methods
# it must work against the class client and servers
# with various drop rates

class Socket:


    def __init__(self):
        # ... your code here ...
        self.mysocket = ip.socket(ip.AF_INET,ip.SOCK_DGRAM)
        self.port = 0
        self.childsocket = 0
        self.mySequenceNumber = 0
        self.OtherSequenceNumber = 0
        self.RTT = 0
        self.transmitqueue = []
        self.ackqueue = []
        self.lastpacketrecived = 0
        self.LPR = 0
        self.clientaddress = 0;
        self.serveraddress = 0
        pass 

    # Print a debugging statement line
    # 
    # 0 == no debugging, greater numbers are more detail.
    # You do not need to implement the body of this method,
    # but it must be in the library.
    def set_debug_level(self, level):
        pass 

    # Set the % likelihood to drop a packet
    #
    # you do not need to implement the body of this method,
    # but it must be in the library,
    def set_drop_prob(self, probability):

        pass 

    # Set the seed for the random number generator to get
    # a consistent set of random numbers
    # 
    # You do not need to implement the body of this method,
    # but it must be in the library.
    def set_random_seed(self, seed):
        self.random_seed = seed 
        

    # bind the address to a port
    # You must implement this method
    #
    def bind(self,address):
        self.mysocket.bind((address))
        pass 

    # connect to a remote port
    # You must implement this method

    ##Connect is referring to the processing of randomizing the sequence number and passing
    #the first set of messages. In this function, first a packet will be delivered with a random sequence
    #number with be generated by the client and send to the server using normal socket sendto, the server responds with an ack
    #and the client responds again with an ack, hence both server and client agree upon a set of sequence numbers to be used


    #Not dealing with drops or timing







    def connect(self,address):
       self.mysocket.setsockopt(ip.SOL_SOCKET, ip.SO_SNDBUF, 8192)
       self.serveraddress = address
       self.sendtomyversion(0,0,address)
       self.recvfrommyverison(0,2)
       self.sendtomyversion(0,2,address)
      # print(self.mySequenceNumber)
      # print(self.otherSequenceNumber)
      # print(self.serveraddress)
      # print(self.clientaddress)
      # print('connected!')
       pass














    #accept a connection
    def accept(self):
        self.mysocket.setsockopt(ip.SOL_SOCKET, ip.SO_SNDBUF, 8192)
        self.recvfrommyverison(0,0)
        self.sendtomyversion(0,1,self.clientaddress)
        self.recvfrommyverison(0,1)
      #  print(self.mySequenceNumber)
      #  print(self.otherSequenceNumber)
      #  print(self.clientaddress)
      #  print(self.serveraddress)
      #  print('accepted')
        pass


    def sendtomyversion(self,buffer,mode,address):
        #synchro mode, from client
        if mode == 0:
            SYNPacket = Packet()
            SYNPacket.cntl = SYNPacket.cntl | SYN
            SYNPacket.seq = 0x8ecb
            self.mySequenceNumber = SYNPacket.seq
            SYNPacket.ack = 0
            SYNPacket.size = 0
            SYNPacket.toHex()

            self.transmitqueue.append(SYNPacket)
            buffer = SYNPacket.pack()
            self.mysocket.sendto(buffer, address)
        ##synchromode still, from server
        elif mode == 1:
            self.transmitqueue.append(self.lastpacketrecived)
            buffer = self.lastpacketrecived.pack()
            self.mysocket.sendto(buffer, address)

        #dealing with acknowledgements for accept and connect()
        elif mode == 2:

            if len(self.transmitqueue) == 0:
                #print('reached')
                buffer = self.lastpacketrecived.pack()
                self.mysocket.sendto(buffer, address)


        #sending any data, this function checks whether or not whether we are attempting to send an ack or a message
        elif mode == 3:
         if LPR == None:
          if len(self.transmitqueue) == 0:
            newPacket = Packet()
            newPacket.ctnl = newPacket.cntl | DATA
            self.mySequenceNumber += 1
            newPacket.seq = self.mySequenceNumber
            newPacket.ack = 0
            newPacket.size = len(buffer)
            newPacket.data = buffer
            newPackedPacket = newPacket.pack()
            self.mysocket.send(newPackedPacket,self.serveraddress)
            self.transmitqueue.append(newPacket)



    def recvfrommyverison(self,nbytes,mode):

        #syncromode, from server recieve packet and set it up
        if mode == 0:
            buffer = self.mysocket.recvfrom(1000)
            packet = Packet()
            packet.unpack(buffer[0])
            self.otherSequenceNumber = packet.seq
            packet.ack = packet.seq
            packet.cntl = packet.cntl | ACK
            packet.seq = 0x2be6
            self.mySequenceNumber = packet.seq
            self.lastpacketrecived = packet
            self.clientaddress = buffer[1]
            #print(packet.ack)
            #print(packet.seq)

        ##This function deals with getting recving the data, and comparing
        elif mode == 1:
            buffer = self.mysocket.recvfrom(1000)
            packet = Packet()
            packet.unpack(buffer[0])
            flag = False
            for i in range(len(self.transmitqueue)):
               # print(self.transmitqueue[i].seq)
               # print(packet.seq)
                if self.transmitqueue[i].seq == packet.ack:
                    self.transmitqueue.remove(self.transmitqueue[i])
                    flag = True
            if (flag == False):
               # print('Problem')
                 a = 7
            packet.cntl = packet.cntl & ACK
            packet.ack = packet.seq
            packet.seq = 0
            self.lastpacketrecived = packet
        # synchromode, from client view, similar to general mode of acknowledgment
        elif mode == 2:
            buffer = self.mysocket.recvfrom(1000)
            packet = Packet()
            packet.unpack(buffer[0])
            self.serveraddress = buffer[1]
            flag = False
            for i in range(len(self.transmitqueue)):
               # print(self.transmitqueue[i].seq)
                #print(packet.seq)
                if self.transmitqueue[i].seq == packet.ack:
                    self.transmitqueue.remove(self.transmitqueue[i])
                    flag = True
            if(flag == False):
              #  print('Problem')
                 a = 7
            packet.cntl = packet.cntl | ACK
            self.otherSequenceNumber = packet.seq
            packet.ack = packet.seq
            packet.seq = 0
            self.lastpacketrecived = packet


        elif mode == 4:
            buffer = self.mysocket.recvfrom(1000)
            packet = Packet()
            packet.unpack(buffer[0])


    def initalconnect(self, address):
        SYNPacket = Packet()
        SYNPacket.cntl = SYNPacket.cntl | SYN
        SYNPacket.seq = 0x8ecb
        self.mySequenceNumber = SYNPacket.seq
        SYNPacket.ack = 0
        SYNPacket.size = 0
        SYNPacket.toHex()

        buffer = SYNPacket.pack()
        self.mysocket.sendto(buffer, address)
        send_time = time.time()
        ##Code above deals with sending the inital packet, now lets receive and send the follow up packet

        buffer = self.mysocket.recvfrom(1000)
        receive_time = time.time()
        RTT = float(receive_time) - float(send_time)
        self.RTT = RTT

        # Receive packet and send it back again,
        packet = Packet()
        packet.unpack(buffer[0])
        if (packet.cntl != SYN | ACK):
          #  print('Big problem big problem!')
             i = 6
        self.otherSequenceNumber = packet.seq
        packet.ack = packet.seq
        packet.seq = 0
        packet.cntl = packet.cntl & ACK
        packet.toHex()
        packet = packet.pack()
        self.mysocket.sendto(packet, buffer[1])

    def initalaccept(self):
        buffer = self.mysocket.recvfrom(1000)
        packet = Packet()
        packet.unpack(buffer[0])
        if packet.cntl != SYN:
           # print('Something happened boooo!')
            a = 7
        self.mySequenceNumber = packet.seq
        packet.ack = packet.seq
        packet.seq = 0x2be6
        self.OtherSequenceNumber = packet.seq
        packet.cntl = packet.cntl | ACK
        packet.toHex()
        packet = packet.pack()
        self.mysocket.sendto(packet, buffer[1])

        buffer = self.mysocket.recvfrom(1000)
        packet = Packet()
        packet.unpack(buffer[0])
        if (packet.cntl != ACK):
           # print('Problem on the high seas! ')
             a = 6


    class transmittingThread(threading.Thread):
        def __init__(self,delay):
            self.name = 'transmittingThread'
            self.delay = delay

        def run(self):
            a = 6





    # send a message up to MAX_DATA
    # You must implement this method


    #here we just send what is necessary, by creating the neceessary packet, incrementing the number and then sending the packet over
    def sendto(self,buffer):

        if len(self.ackqueue) != 0:
            while len(self.ackqueue) > 0:
             for i in range(len(self.ackqueue)):
                newPacket = self.ackqueue[i]
                newPacket.cntl = ACK
                newPacket.ack = newPacket.seq
                newPacket.seq = 0
                newPacket.data = b''
                newPacket.size = 0
                newPacket.toHex
                newPackedPacket = newPacket.pack()
                if(self.serveraddress == 0):
                    self.mysocket.sendto(newPackedPacket, self.clientaddress)
                else:
                 a = 6
                 self.mysocket.sendto(newPackedPacket, self.serveraddress)
                self.ackqueue.remove(self.ackqueue[i])
                break



        newPacket = Packet()
        newPacket.data = buffer
        newPacket.size = len(buffer)
        newPacket.cntl = newPacket.cntl | DATA
        self.mySequenceNumber += 1
        newPacket.seq = self.mySequenceNumber
        newPacket.ack = 0
        newPacket.toHex()
        newPackedPacket = newPacket.pack()
        if(self.serveraddress == 0):
            self.mysocket.sendto(newPackedPacket, self.clientaddress)
        elif self.clientaddress == 0:
            self.mysocket.sendto(newPackedPacket, self.serveraddress)
        self.transmitqueue.append(newPacket)



        pass






# receive a message up to MAX_DATA
    # You must implement this method


    # Basically keep polling, first we check whether or not we need any future acks from messages we've sent in the past, if not then we simply just
    # keep waiting until we get the message that is to be expected, once both conditions are fulfilled, or one of them then recv returns, otherwise it keeps blocking
    def recvfrom(self,nbytes):

      Flag = True
      while Flag:
      # print('stuck in recv loop')
       buffer = self.mysocket.recvfrom(MAX_SIZE)
      # print('kj % i' % nbytes)
       packet = Packet()
       packet.unpack(buffer[0])
       flag1 = False
       flag2 = False

       if(len(self.transmitqueue) == 0):
           flag2 = True
       else:
        for i in range(len(self.transmitqueue)):
          # print(self.transmitqueue[i].seq)
          # print(packet.seq)
          # print(i)
          if self.transmitqueue[i].seq == packet.ack:
              self.transmitqueue.remove(self.transmitqueue[i])
              break



       expectedseq = self.otherSequenceNumber
      # print(expectedseq)
      # print(packet.seq)
       if packet.seq == expectedseq+1:
           self.otherSequenceNumber += 1
           a = 6
           self.ackqueue.append(packet)
          # print('EXITED recv loop')
           return packet.data
       pass



    #This function deals with sending the closing packets, however another function is called just before that deals with any outstanding packets
    def sendclosingpacket(self):
        if len(self.ackqueue) != 0:
            while len(self.ackqueue) > 0:
             for i in range(len(self.ackqueue)):
                newPacket = self.ackqueue[i]
                newPacket.cntl = ACK
                newPacket.ack = newPacket.seq
                newPacket.seq = 0
                newPacket.data = b''
                newPacket.size = 0
                newPacket.toHex
                newPackedPacket = newPacket.pack()
                if(self.serveraddress == 0):
                    self.mysocket.sendto(newPackedPacket, self.clientaddress)
                else:
                 a = 6
                 self.mysocket.sendto(newPackedPacket, self.serveraddress)
                self.ackqueue.remove(self.ackqueue[i])
                break






        packet = Packet()
        packet.cntl = packet.cntl | FIN
        packet.ack = 0
        self.mySequenceNumber += 1
        packet.seq = self.mySequenceNumber
        packet.toHex()
        newPackedPacket = packet.pack()
        if (self.serveraddress == 0):
            self.mysocket.sendto(newPackedPacket, self.clientaddress)
        elif self.clientaddress == 0:
            self.mysocket.sendto(newPackedPacket, self.serveraddress)
        self.transmitqueue.append(packet)


    def recvfromforclosing(self):
        Flag = True
        while Flag:
           # print('stuck in recv loop')
            buffer = self.mysocket.recvfrom(MAX_SIZE)
            packet = Packet()
            packet.unpack(buffer[0])
            flag1 = False
            flag2 = False

            if (len(self.transmitqueue) == 0):
                flag2 = True
            else:
                for i in range(len(self.transmitqueue)):
                    # print(self.transmitqueue[i].seq)
                    # print(packet.seq)
                   # print(i)
                    if self.transmitqueue[i].seq == packet.ack:
                        self.transmitqueue.remove(self.transmitqueue[i])
                       # print('reached')
                        break

            expectedseq = self.otherSequenceNumber
           # print(expectedseq)
           # print(packet.seq)

            if packet.seq == expectedseq + 1:
                 self.otherSequenceNumber += 1
                 a = 6
                 self.ackqueue.append(packet)
               #  print('EXITED recv loop')
                 return packet.data






    # close the socket and make sure all outstanding
    # data is delivered 
    # You must implement this method         
    def close(self):
       # print('inside close')
        self.sendclosingpacket()
        self.recvfromforclosing()
        pass
        
# Example how to start a start the timeout thread
global sock352_dbg_level 
sock352_dbg_level = 0
dbg_print(3,"starting timeout thread")

# create the thread 
thread1 = sock352Thread(1, "Thread-1", 0.25)

# you must make it a daemon thread so that the thread will
# exit when the main thread does. 
thread1.daemon = True

# run the thread 
thread1.start()


