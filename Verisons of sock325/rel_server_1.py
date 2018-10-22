#!/usr/bin/python

# echo server for CS 352 
# (c) 2018, R. P. Martin, under GPL Version 2

# this sever echos back whatever it gets, up to the max of sock352.MAX_SIZE

import argparse
import time
import struct 
import md5
import os 
import sock352


MAX_SIZE = (63*1024)



def main():
    # parse all the arguments to the client 
    parser = argparse.ArgumentParser(description='CS 352 Socker Echo Server ')
    parser.add_argument('-l','--localport', help='local sock352 UDP port', required=True)
    parser.add_argument('-x','--debuglevel', help='Debug Level')
    parser.add_argument('-z','--dropprob', help='Drop Probability')
    
    args = vars(parser.parse_args())
    local_port =  int(args['localport'])


    # set the debug level. 0 = no debug statements, 10 = maximum debug output 
    if (args['debuglevel'] == None):
        debug_level = 0
    else:
        debug_level =  int(args['debuglevel'])


    # set the drop probability. 0.0 = no data drops, 1.0 = drop everything 
    if (args['dropprob'] == None):
        probability =  0.0
    else:
        probability =  float(args['dropprob'])


    serverSock = sock352.Socket()
    serverSock.bind(('', local_port))

    # set the debug level in the library
    serverSock.set_random_seed(352)
    serverSock.set_debug_level(debug_level)
    serverSock.set_drop_prob(probability)

    from_addr = serverSock.accept()
    
    num_lines_str = serverSock.recvfrom(1000)
    line_count = int(num_lines_str)
    print ("server -- will echo %d lines " % (line_count))
    
    while (line_count > 0):
        #Read from UDP socket into message, client address 
        message = serverSock.recvfrom(MAX_SIZE)
        print ("server -- got packet len %d line %s" % (len(message),message))
        serverSock.sendto(message)
        line_count = line_count - 1
        print ("server -- %d lines to go " % (line_count))
        
    serverSock.close()

# this gives a main function in Python
if __name__ == "__main__":
    main()
