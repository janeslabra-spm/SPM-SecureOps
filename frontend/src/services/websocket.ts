/**
 * WebSocket connection manager for real-time incident notifications.
 * Connects to /ws/incidents with automatic reconnection (5-second retry).
 */

export type WebSocketMessage = Record<string, unknown>;

export type WebSocketEventHandler = {
  onMessage?: (data: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
};

export class WebSocketManager {
  private socket: WebSocket | null = null;
  private url: string;
  private handlers: WebSocketEventHandler;
  private reconnectInterval = 5000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = true;

  constructor(url: string, handlers: WebSocketEventHandler = {}) {
    this.url = url;
    this.handlers = handlers;
  }

  /** Open the WebSocket connection */
  connect(): void {
    this.shouldReconnect = true;
    this.createConnection();
  }

  /** Close the connection and stop reconnection attempts */
  disconnect(): void {
    this.shouldReconnect = false;
    this.clearReconnectTimer();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  /** Check if the WebSocket is currently connected */
  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /** Get current connection state */
  get readyState(): number | null {
    return this.socket?.readyState ?? null;
  }

  private createConnection(): void {
    try {
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        console.log("[WebSocket] Connected to", this.url);
        this.handlers.onOpen?.();
      };

      this.socket.onmessage = (event: MessageEvent) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          this.handlers.onMessage?.(data);
        } catch (parseError) {
          console.error("[WebSocket] Failed to parse message:", parseError);
        }
      };

      this.socket.onclose = () => {
        console.log("[WebSocket] Disconnected from", this.url);
        this.handlers.onClose?.();
        this.scheduleReconnect();
      };

      this.socket.onerror = (error: Event) => {
        console.error("[WebSocket] Error:", error);
        this.handlers.onError?.(error);
      };
    } catch (error) {
      console.error("[WebSocket] Connection failed:", error);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;
    this.clearReconnectTimer();
    this.reconnectTimer = setTimeout(() => {
      console.log("[WebSocket] Attempting reconnection...");
      this.createConnection();
    }, this.reconnectInterval);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

/** Default WebSocket URL for incident notifications */
export const WS_INCIDENTS_URL = "ws://localhost:8000/ws/incidents";
