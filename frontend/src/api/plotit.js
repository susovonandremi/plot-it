import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
     baseURL: API_BASE_URL
});

let getTokenFn = null;
export const setAuthTokenGetter = (fn) => {
     getTokenFn = fn;
};

api.interceptors.request.use(async (config) => {
     if (getTokenFn) {
          try {
               const token = await getTokenFn();
               if (token) {
                    config.headers.Authorization = `Bearer ${token}`;
               }
          } catch (e) {
               console.error("Failed to get auth token:", e);
          }
     }
     return config;
});

export const parsePrompt = async (prompt) => {
     try {
          const response = await api.post(`/api/v1/parse`, { prompt });
          return response.data.data;
     } catch (error) {
          console.error("Error parsing prompt:", error);
          throw error;
     }
};

export const generateBlueprint = async (requestData) => {
     try {
          // requestData should match GenerateRequest schema:
          // { plot_size_sqft, floors, rooms, user_tier, original_unit_system }
          const response = await api.post(`/api/v1/generate`, requestData);
          return response.data.data;
     } catch (error) {
          console.error("Error generating blueprint:", error);
          throw error;
     }
};

export const generateBlueprintStream = (requestData, onMessage) => {
     let ws = null;
     let heartbeatTimer = null;
     let didComplete = false;
     let didSettle = false; // true once promise resolved or rejected

     // Heartbeat: if no message arrives for HEARTBEAT_MS, assume stall
     const HEARTBEAT_MS = 15000;

     const promise = new Promise((resolve, reject) => {
          const settle = (fn, value) => {
               if (didSettle) return;
               didSettle = true;
               clearTimeout(heartbeatTimer);
               fn(value);
          };

          const resetHeartbeat = () => {
               clearTimeout(heartbeatTimer);
               heartbeatTimer = setTimeout(() => {
                    console.warn("WebSocket heartbeat timeout — no message for 15s.");
                    try { ws?.close(); } catch (_) {}
                    settle(reject, new Error("WebSocket stream timed out (no heartbeat for 15 seconds)"));
               }, HEARTBEAT_MS);
          };

          const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/api/v1/stream/generate';
          ws = new WebSocket(wsUrl);

          ws.onopen = async () => {
               // Append token if available
               let payload = { ...requestData };
               if (getTokenFn) {
                    try {
                         const token = await getTokenFn();
                         if (token) {
                              payload.token = token; // Add token directly to message payload for WS authentication
                         }
                    } catch (e) {
                         console.error("WS auth token retrieval failed:", e);
                    }
               }
               ws.send(JSON.stringify(payload));
               resetHeartbeat();
          };

          ws.onmessage = (event) => {
               resetHeartbeat();
               try {
                    const { event: eventName, data } = JSON.parse(event.data);
                    onMessage(eventName, data);
                    if (eventName === 'complete') {
                         didComplete = true;
                         settle(resolve, data);
                         try { ws.close(); } catch (_) {}
                    }
                    if (eventName === 'error') {
                         settle(reject, new Error(data?.message || 'Stream error'));
                         try { ws.close(); } catch (_) {}
                    }
               } catch (e) {
                    console.error("Error parsing WS message", e);
               }
          };

          ws.onerror = () => {
               settle(reject, new Error("WebSocket connection failed. Check that the backend server is running on " + wsUrl));
          };
          
          ws.onclose = (event) => {
               clearTimeout(heartbeatTimer);
               // If the server closed cleanly but never sent 'complete',
               // reject so the REST fallback in Home.jsx kicks in.
               if (!didComplete && !didSettle) {
                    settle(reject, new Error(
                         event.code !== 1000 && event.code !== 1005
                              ? `WebSocket closed unexpectedly (code ${event.code}): ${event.reason || 'No reason provided'}`
                              : 'WebSocket closed without sending completion event'
                    ));
               }
          };
     });

     const abort = () => {
          clearTimeout(heartbeatTimer);
          if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
               try { ws.close(); } catch (_) {}
          }
     };

     return { promise, abort, get didComplete() { return didComplete; } };
};

export const recommendRooms = async (plotData, answers) => {
     try {
          const response = await api.post(`/api/v1/consultation/recommend`, {
               plot_size_sqft: plotData.plot_size_sqft,
               plot_width_ft: plotData.plot_width_ft,
               plot_depth_ft: plotData.plot_depth_ft,
               entry_direction: plotData.entry_direction,
               answers: answers
          });
          return response.data.data;
     } catch (error) {
          console.error("Error getting room recommendations:", error);
          throw error;
     }
};
