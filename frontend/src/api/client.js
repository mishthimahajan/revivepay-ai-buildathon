import axios from "axios";

const apiBaseURL =
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

const apiClient = axios.create({
  baseURL: apiBaseURL.replace(/\/$/, ""),
  timeout: 90000,
  headers: {
    Accept: "application/json",
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === "ECONNABORTED") {
      error.userMessage =
        "The backend is waking up. Please wait a moment and try again.";
    } else if (!error.response) {
      error.userMessage =
        "Could not connect to the backend service.";
    }

    return Promise.reject(error);
  },
);

export default apiClient;