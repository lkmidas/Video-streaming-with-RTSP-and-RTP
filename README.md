# Video Streaming with RTSP and RTP
This is my assignment for HCMUT Computer Engineering course CO3003 - *Computer Networking*: **Making a client-server video streaming app using RTSP and RTP**. More details are in the report file (written in English).

## Introduction
This application uses a simplified version of RTSP and RTP to stream a video from a server to a client. The only supported video format is mjpeg. Some extended functionalities to calculate some performance metrics are also included.

## Files
- `Client.py` and `Client3Btn.py`: where the client is implemented (original 4-button version and 3-button version).
- `ClientLauncher.py` and `ClientLauncher3Btn.py`: launcher to take in arguments and spawn the client.
- `ServerWorker.py`: where the server is implemented.
- `Server.py`: launcher to spawn the server.
- `RtpPacket.py`: where RTP packets are encoded/decoded.
- `VideoStream.py`: helper class to parse mjpeg files.

## Usage
To launch the server:
```
python3 Server.py <server_port>
```
To launch the client:
```
python3 ClientLauncher.py <server_host> <server_port> <RTP_port> <video_file>
or
python3 ClientLauncher3Btn.py <server_host> <server_port> <RTP_port> <video_file>
```

## Implementation Details
See `Report.pdf`.
