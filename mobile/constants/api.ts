import Constants from "expo-constants";

function getApiBase(): string {
  if (process.env.EXPO_PUBLIC_API_URL) return process.env.EXPO_PUBLIC_API_URL;

  // Try every field Expo has used across SDK versions
  const host =
    Constants.expoConfig?.hostUri?.split(":")[0] ||
    (Constants.manifest as any)?.debuggerHost?.split(":")[0] ||
    (Constants.manifest2 as any)?.extra?.expoGo?.debuggerHost?.split(":")[0];

  const base = host ? `http://${host}:8080` : "http://localhost:8080";
  console.log("[api] API_BASE:", base, "| raw hostUri:", Constants.expoConfig?.hostUri);
  return base;
}

export const API_BASE = getApiBase();
export const DEMO_USER_ID = "00000000-0000-0000-0000-000000000001";
