
import subprocess
import time
import traceback

from socket_wrapper import Server

spoof_process: subprocess.Popen


def start_spoofing(host_ip: str,target_ip: str,router_ip: str) -> None:
    """
    ths function will start a process that spams spoofed packets.
    """
    global spoof_process
    spoof_process = subprocess.Popen(["python","spoof.py",host_ip,target_ip,router_ip])


def stop_spoofing() -> None:
    """
    stop spoofing, by killing spoofer process.
    """
    print("Killing spoofer....")
    try:
        spoof_process.terminate()
        time.sleep(0.5)
        print("Process killed")
    except Exception as e:
        print("couldn't kill process")
        print(str(e))


def main():

    host_ip, target_ip,router_ip = "192.168.1.128","192.168.1.128","192.168.1.1"
    start_spoofing(host_ip, target_ip,router_ip)
    
    server: Server = Server(12344)
    try:
        while True:
            
            from_client: bytes  = server.recv_by_size()
            if not from_client:
                break
            to_send = server.parse(from_client)
            
            server.send_by_size(to_send)
        
        
    except Exception as err:
        print(f'General error: {err}')
        print(traceback.format_exc())
    finally:
        server.cleanup()
        stop_spoofing()


if __name__ == "__main__":
    main()