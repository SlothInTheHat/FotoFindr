import Constants from "expo-constants";

function getApiBase(): string {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;
  // Reuse the IP Expo already knows (e.g. "10.195.25.243:8081" → backend on :8080)
  const host = Constants.expoConfig?.hostUri?.split(":")[0];
  if (host) return `http://${host}:8080`;
  return "http://localhost:8080";
}

export const API_BASE = getApiBase();
export const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";
