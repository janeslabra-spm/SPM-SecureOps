import { useEffect, useRef, useState, useCallback } from "react";
import {
  WebSocketManager,
  WebSocketMessage,
  WS_INCIDENTS_URL,
} from "../services/websocket";

export type ConnectionState = "connecting" | "connected" | "disconnected";

interface UseWebSocketOptions {
  /** WebSocket URL (defaults to ws://localhost:8000/ws/incidents) */
  url?: string;
  /** Whether to connect automatically on mount (default: true) */
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  /** Current connection state */
  connectionState: ConnectionState;
  /** Most recent message received */
  lastMessage: WebSocketMessage | null;
  /** All messages received since last connection */
  messages: WebSocketMessage[];
  /** Manually connect to the WebSocket */
  connect: () => void;
  /** Manually disconnect from the WebSocket */
  disconnect: () => void;
}

/**
 * Custom hook for WebSocket connection management.
 * Exposes connection state and incoming messages from /ws/incidents.
 */
export function useWebSocket(
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const { url = WS_INCIDENTS_URL, autoConnect = true } = options;

  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const managerRef = useRef<WebSocketManager | null>(null);

  const connect = useCallback(() => {
    if (managerRef.current) {
      managerRef.current.disconnect();
    }

    setConnectionState("connecting");

    const manager = new WebSocketManager(url, {
      onOpen: () => setConnectionState("connected"),
      onClose: () => setConnectionState("disconnected"),
      onMessage: (data) => {
        setLastMessage(data);
        setMessages((prev) => [...prev, data]);
      },
      onError: () => setConnectionState("disconnected"),
    });

    manager.connect();
    managerRef.current = manager;
  }, [url]);

  const disconnect = useCallback(() => {
    managerRef.current?.disconnect();
    managerRef.current = null;
    setConnectionState("disconnected");
  }, []);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      managerRef.current?.disconnect();
      managerRef.current = null;
    };
  }, [autoConnect, connect]);

  return { connectionState, lastMessage, messages, connect, disconnect };
}
