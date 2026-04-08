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
     return new Promise((resolve, reject) => {
          const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/api/v1/stream/generate';
          const ws = new WebSocket(wsUrl);

          ws.onopen = () => {
               ws.send(JSON.stringify(requestData));
          };

          ws.onmessage = (event) => {
               try {
                    const { event: eventName, data } = JSON.parse(event.data);
                    onMessage(eventName, data);
                    if (eventName === 'complete') {
                         resolve(data);
                         ws.close();
                    }
                    if (eventName === 'error') {
                         reject(new Error(data.message));
                         ws.close();
                    }
               } catch (e) {
                    console.error("Error parsing WS message", e);
               }
          };

          ws.onerror = (event) => {
               reject(new Error("WebSocket connection failed. Check that the backend server is running on " + wsUrl));
          };
          
          ws.onclose = (event) => {
               // If closed before resolving, reject with a meaningful error
               if (event.code !== 1000 && event.code !== 1005) {
                    reject(new Error(`WebSocket closed unexpectedly (code ${event.code}): ${event.reason || 'No reason provided'}`));
               }
          };
     });
};

export const recommendRooms = async (plotData, answers) => {
     try {
          const response = await axios.post(`${API_BASE_URL}/api/v1/consultation/recommend`, {
               plot_size_sqft: plotData.plot_size_sqft,
               orientation: plotData.orientation,
               answers: answers
          });
          return response.data.data;
     } catch (error) {
          console.error("Error getting room recommendations:", error);
          throw error;
     }
};
