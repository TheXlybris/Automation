import { io } from 'socket.io-client';

let socketInstance = null;

export function getSocket() {
  if (!socketInstance) {
    socketInstance = io(window.location.origin);
  }
  return socketInstance;
}

export function disconnectSocket() {
  if (socketInstance) {
    socketInstance.disconnect();
    socketInstance = null;
  }
}

// Emit with promise — wait for server response
export function socketEmit(event, data, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const socket = getSocket();
    const timer = setTimeout(() => reject(new Error(`Timeout on ${event}`)), timeout);
    
    // Emit with callback
    socket.emit(event, data, (response) => {
      clearTimeout(timer);
      resolve(response);
    });
  });
}
