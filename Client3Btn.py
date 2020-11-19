from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
SESSION_FILE = "session.txt"

class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT
    
    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    DESCRIBE = 4
    
    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, fileName):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = fileName
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0

        self.bytesReceived = 0
        self.startTime = 0
        self.lossCounter = 0
        self.firstPlay = True
        
    def createWidgets(self):
        """Build GUI."""
        # Create Play button        
        self.start = Button(self.master, width=15, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=0, padx=2, pady=2)
        self.start["state"] = "normal"
        
        # Create Pause button            
        self.pause = Button(self.master, width=15, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=1, padx=2, pady=2)
        self.pause["state"] = "disabled"
        
        # Create Stop button
        self.stop = Button(self.master, width=15, padx=3, pady=3)
        self.stop["text"] = "Stop"
        self.stop["command"] =  self.exitClient
        self.stop.grid(row=2, column=2, padx=2, pady=2)
        self.stop["state"] = "disabled"

        # Create Describe button
        self.describe = Button(self.master, width=15, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] =  self.describeSession
        self.describe.grid(row=1, column=2, padx=2, pady=2)
        self.describe["state"] = "disabled"
        
        # Create a label to display the movie
        self.label = Label(self.master, height=18, bg="black")
        self.label.grid(row=0, column=0, columnspan=3, sticky=W+E+N+S, padx=5, pady=5) 

        # Create a label to display the time
        self.timeBox = Label(self.master, width=12, text="00:00")
        self.timeBox.grid(row=1, column=1, columnspan=1, sticky=W+E+N+S, padx=5, pady=5)
    
    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)
    
    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)  

        if self.frameNbr != 0:
            lossRate = self.lossCounter / self.frameNbr
            print("[*]RTP Packet Loss Rate: " + str(lossRate) +"\n")

        self.master.destroy() # Close the gui window
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)
    
    def playMovie(self):
        """Play button handler."""
        # If it's the first time PLAY is clicked, send SETUP
        if self.state == self.INIT and self.firstPlay:
            self.sendRtspRequest(self.SETUP)
            self.firstPlay = False
            # Wait until ready
            while self.state != self.READY:
                pass

        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)
    
    def describeSession(self):
        """Describe button handler."""
        self.sendRtspRequest(self.DESCRIBE)
    
    def listenRtp(self):        
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    # If sequence number doesn't match, we have a packet loss
                    if self.frameNbr + 1 != rtpPacket.seqNum():
                        self.lossCounter += (rtpPacket.seqNum() - (self.frameNbr + 1))
                        print("[*]Packet loss!")
                    
                    currFrameNbr = rtpPacket.seqNum()
                    print("Current Seq Num: " + str(currFrameNbr))
                                        
                    if currFrameNbr > self.frameNbr: # Discard the late packet
                        # Count the received bytes
                        self.bytesReceived += len(rtpPacket.getPayload())
                        
                        self.frameNbr = currFrameNbr
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))

                        # Show the current streaming time
                        currentTime = int(currFrameNbr * 0.05)
                        self.timeBox.configure(text="%02d:%02d" % (currentTime // 60, currentTime % 60))
                        
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet(): 
                    break
                
                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break
                    
    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()
        
        return cachename
    
    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image = photo, height=288) 
        self.label.image = photo
        
    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkinter.messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
    
    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""    
        #-------------
        # TO COMPLETE
        #-------------
        
        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            # Update RTSP sequence number.
            self.rtspSeq = 1
            
            # Write the RTSP request to be sent.
            request = "SETUP " + str(self.fileName) + " RTSP/1.0\n"
            request += "CSeq: " + str(self.rtspSeq) + "\n"
            request += "Transport: RTP/UDP; client_port= " + str(self.rtpPort)
            
            # Keep track of the sent request.
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = "PLAY " + str(self.fileName) + " RTSP/1.0\n"
            request += "CSeq: " + str(self.rtspSeq) + "\n"
            request += "Session: " + str(self.sessionId)
            
            # Keep track of the sent request.
            self.requestSent = self.PLAY
        
        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = "PAUSE " + str(self.fileName) + " RTSP/1.0\n"
            request += "CSeq: " + str(self.rtspSeq) + "\n"
            request += "Session: " + str(self.sessionId)
            
            # Keep track of the sent request.
            self.requestSent = self.PAUSE
            
        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = "TEARDOWN " + str(self.fileName) + " RTSP/1.0\n"
            request += "CSeq: " + str(self.rtspSeq) + "\n"
            request += "Session: " + str(self.sessionId)
            
            # Keep track of the sent request.
            self.requestSent = self.TEARDOWN

        # Describe request
        elif requestCode == self.DESCRIBE and not self.state == self.INIT:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            
            # Write the RTSP request to be sent.
            request = "DESCRIBE " + str(self.fileName) + " RTSP/1.0\n"
            request += "CSeq: " + str(self.rtspSeq) + "\n"
            request += "Session: " + str(self.sessionId)
            
            # Keep track of the sent request.
            self.requestSent = self.DESCRIBE

        else:
            return
        
        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode())
        
        print('\nData sent:\n' + request)
    
    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)
            
            if reply: 
                self.parseRtspReply(reply.decode("utf-8"))
            
            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break
    
    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])
        
        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0:
                self.sessionId = session
            
            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200: 
                    if self.requestSent == self.SETUP:
                        #-------------
                        # TO COMPLETE
                        #-------------
                        # Update RTSP state.
                        self.state = self.READY
                        
                        # Open RTP port.
                        self.openRtpPort() 

                    elif self.requestSent == self.PLAY:
                        # Update RTSP state.
                        self.state = self.PLAYING

                        # Start counting received bytes
                        self.startTime = time.time()
                        self.bytesReceived = 0

                        # Update buttons' states
                        self.start["state"] = "disabled"
                        self.pause["state"] = "normal"
                        self.stop["state"] = "normal"
                        self.describe["state"] = "normal"

                    elif self.requestSent == self.PAUSE:
                        # Update RTSP state.
                        self.state = self.READY
                        
                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()

                        # Calculate the video data rate
                        dataRate = int(self.bytesReceived / (time.time() - self.startTime))
                        print("[*]Video data rate: " + str(dataRate) + " bytes/sec\n")

                        # Update buttons' states
                        self.start["state"] = "normal"
                        self.pause["state"] = "disabled"
                        self.stop["state"] = "normal"

                    elif self.requestSent == self.TEARDOWN:
                        # Update RTSP state.
                        self.state = self.INIT
                        
                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1 

                    elif self.requestSent == self.DESCRIBE:
                        # Write RTSP payload to session file
                        f = open(SESSION_FILE, "w")
                        for i in range(4, len(lines)):
                            f.write(lines[i] + '\n')
                        f.close()
    
    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        #-------------
        # TO COMPLETE
        #-------------
        # Create a new datagram socket to receive RTP packets from the server
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)
        
        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.rtpSocket.bind(("0.0.0.0", self.rtpPort))
        except:
            tkinter.messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else: # When the user presses cancel, resume playing.
            self.playMovie()
