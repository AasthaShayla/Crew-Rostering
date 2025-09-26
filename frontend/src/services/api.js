import axios from 'axios';
import io from 'socket.io-client';

// Prefer explicit env, else default to backend dev port 5050
const ENV_BASE = process.env.REACT_APP_API_URL;
const DEFAULT_BASE = 'http://localhost:5050';
const BASE_URL = ENV_BASE || DEFAULT_BASE;
const API_BASE_URL = `${BASE_URL}/api`;

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes for optimization requests
  headers: {
    'Content-Type': 'application/json',
  },
});

// Socket.IO connection
let socket = null;

export const connectSocket = () => {
  if (!socket) {
    socket = io(BASE_URL, {
      // Force HTTP long-polling to avoid Werkzeug websocket 500:
      // "AssertionError: write() before start_response"
      transports: ['polling'],
      upgrade: false,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 500,
      reconnectionDelayMax: 5000,
      timeout: 10000
    });

    // Basic diagnostics to reduce transient console noise
    socket.on('connect_error', (err) => {
      console.warn('Socket connect_error:', err?.message || err);
    });
    socket.io.on('reconnect_attempt', (attempt) => {
      if (attempt % 5 === 0) {
        console.log('Socket reconnect attempt:', attempt);
      }
    });
    socket.on('disconnect', (reason) => {
      console.warn('Socket disconnected:', reason);
    });
  }
  return socket;
};

export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
};

// Fallback helpers (handle wrong env or port)
const directGet = (path) => axios.get(`http://localhost:5050/api${path}`, { timeout: 120000 });
const directPost = (path, body) => axios.post(`http://localhost:5050/api${path}`, body, { timeout: 120000 });

// API endpoints with resilient fallbacks
export const apiService = {
  // Health check
  healthCheck: async () => {
    try {
      return await api.get('/health');
    } catch (e) {
      return await directGet('/health');
    }
  },

  // Data endpoints
  getFlights: async () => {
    try {
      return await api.get('/data/flights');
    } catch (e) {
      console.warn('getFlights() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directGet('/data/flights');
    }
  },
  getCrew: async () => {
    try {
      return await api.get('/data/crew');
    } catch (e) {
      console.warn('getCrew() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directGet('/data/crew');
    }
  },

  // Optimization endpoints
  optimize: async (params = {}) => {
    const defaultParams = {
      weights: { w_ot: 100, w_fair: 10, w_pref: 1, w_base: 50, w_continuity: 75 },
      max_time: 30 // 30 seconds for quick results with minimal dataset
    };
    const body = { ...defaultParams, ...params };
    try {
      return await api.post('/optimize', body);
    } catch (e) {
      console.warn('optimize() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directPost('/optimize', body);
    }
  },

  reoptimize: async (disruptions = {}) => {
    const defaultParams = {
      weights: { w_ot: 100, w_fair: 10, w_pref: 1, w_base: 50, w_continuity: 75 },
      max_time: 30, // 30 seconds for quick what-if scenarios
      flight_disruptions: [],
      crew_sickness: [],
      ...disruptions
    };
    try {
      return await api.post('/reoptimize', defaultParams);
    } catch (e) {
      console.warn('reoptimize() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directPost('/reoptimize', defaultParams);
    }
  },
  // Natural-language disruption parsing (LLM-assisted)
  parseDisruptions: async (text) => {
    const body = { text };
    try {
      return await api.post('/disruptions/parse', body);
    } catch (e) {
      console.warn('parseDisruptions() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directPost('/disruptions/parse', body);
    }
  },

  // Job status
  getJobStatus: async (jobId) => {
    try {
      return await api.get(`/jobs/${jobId}`);
    } catch (e) {
      console.warn('getJobStatus() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directGet(`/jobs/${jobId}`);
    }
  },

  // Roster endpoints
  getCurrentRoster: async () => {
    try {
      return await api.get('/roster/current');
    } catch (e) {
      console.warn('getCurrentRoster() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directGet('/roster/current');
    }
  },
  getBaselineRoster: async () => {
    try {
      return await api.get('/roster/baseline');
    } catch (e) {
      console.warn('getBaselineRoster() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await directGet('/roster/baseline');
    }
  },
  // Weather endpoints
  weatherSummary: async (start, end) => {
    try {
      return await api.get('/weather/summary', { params: { start, end } });
    } catch (e) {
      console.warn('weatherSummary() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await axios.get(`${DEFAULT_BASE}/api/weather/summary`, { params: { start, end }, timeout: 120000 });
    }
  },
  weatherDay: async (date) => {
    try {
      return await api.get('/weather/day', { params: { date } });
    } catch (e) {
      console.warn('weatherDay() primary failed, trying fallback to localhost:5050', e?.message || e);
      return await axios.get(`${DEFAULT_BASE}/api/weather/day`, { params: { date }, timeout: 120000 });
    }
  }
};

// Error interceptor (keep it for better user messages)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    if (error.response?.status === 404) {
      return Promise.reject(new Error('Resource not found'));
    }
    if (error.response?.status >= 500) {
      return Promise.reject(new Error('Server error. Please try again later.'));
    }
    return Promise.reject(error);
  }
);

export default api;