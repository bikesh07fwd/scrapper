/**
 * src/api/client.js — Clean API client wrapper.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function fetchJson(url, options = {}) {
  const response = await fetch(`${API_BASE_URL}${url}`, options);
  
  if (!response.ok) {
    let errorDetail = "API Request failed";
    let errorJson = null;
    try {
      errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // Non-JSON response or missing detail
    }
    
    const err = new Error(errorDetail);
    err.status = response.status;
    err.detail = errorJson;
    throw err;
  }
  
  return response.json();
}

export const getHealth = () => fetchJson("/health");

export const getJobs = (limit = 20, offset = 0) =>
  fetchJson(`/jobs?limit=${limit}&offset=${offset}`);

export const getJob = (id) => fetchJson(`/jobs/${id}`);

export const getRuns = (limit = 20, offset = 0) =>
  fetchJson(`/runs?limit=${limit}&offset=${offset}`);

export const getRun = (id) => fetchJson(`/runs/${id}`);

export const triggerAdapter = (adapter, scenario = null) => {
  const query = scenario ? `?scenario=${scenario}` : "";
  return fetchJson(`/trigger/${adapter}${query}`, {
    method: "POST",
  });
};
