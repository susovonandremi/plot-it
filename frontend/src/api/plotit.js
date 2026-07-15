import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const parsePrompt = async (prompt) => {
     try {
          const response = await axios.post(`${API_BASE_URL}/api/v1/parse`, { prompt });
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
          const response = await axios.post(`${API_BASE_URL}/api/v1/generate`, requestData);
          return response.data.data;
     } catch (error) {
          console.error("Error generating blueprint:", error);
          throw error;
     }
};

export const generateBlueprintStream = (requestData, onMessage) => {
     let ws = null;
     let timeoutId = null;

     const promise = new Promise((resolve, reject) => {
          const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/api/v1/stream/generate';
          ws = new WebSocket(wsUrl);

          timeoutId = setTimeout(() => {
               console.warn("WebSocket generation stream timed out.");
               if (ws) {
                    try {
                         ws.close();
                    } catch (e) {}
               }
               reject(new Error("WebSocket stream timed out after 30 seconds"));
          }, 30000);

          ws.onopen = () => {
               ws.send(JSON.stringify(requestData));
          };

          ws.onmessage = (event) => {
               try {
                    const { event: eventName, data } = JSON.parse(event.data);
                    onMessage(eventName, data);
                    if (eventName === 'complete') {
                         clearTimeout(timeoutId);
                         resolve(data);
                         try {
                              ws.close();
                         } catch (e) {}
                    }
                    if (eventName === 'error') {
                         clearTimeout(timeoutId);
                         reject(new Error(data.message));
                         try {
                              ws.close();
                         } catch (e) {}
                    }
               } catch (e) {
                    console.error("Error parsing WS message", e);
               }
          };

          ws.onerror = (event) => {
               clearTimeout(timeoutId);
               reject(new Error("WebSocket connection failed. Check that the backend server is running on " + wsUrl));
          };
          
          ws.onclose = (event) => {
               clearTimeout(timeoutId);
               if (event.code !== 1000 && event.code !== 1005) {
                    reject(new Error(`WebSocket closed unexpectedly (code ${event.code}): ${event.reason || 'No reason provided'}`));
               }
          };
     });

     const abort = () => {
          clearTimeout(timeoutId);
          if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
               try {
                    ws.close();
               } catch (e) {}
          }
     };

     return { promise, abort };
};

export const recommendRooms = async (plotData, answers) => {
     try {
          const response = await axios.post(`${API_BASE_URL}/api/v1/consultation/recommend`, {
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
