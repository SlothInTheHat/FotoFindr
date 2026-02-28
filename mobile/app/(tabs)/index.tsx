import React, { useState } from "react";
import {
  View,
  Text,
  FlatList,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { API_BASE, DEMO_USER_ID } from "@/constants/api";

type UploadedPhoto = {
  photo_id: string;
  storage_url: string;
  status?: string;
};

export default function UploadScreen() {
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [uploading, setUploading] = useState(false);

  function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function parseApiError(resp: Response) {
    try {
      const payload = await resp.json();
      const detail = payload?.detail;
      if (detail?.error_code && detail?.message) {
        return `${detail.error_code}: ${detail.message}`;
      }
      if (typeof detail === "string") return detail;
      if (payload?.message) return payload.message;
    } catch {
      // Ignore JSON parse failure and fall back to status text.
    }
    return `HTTP_${resp.status}: ${resp.statusText || "Request failed"}`;
  }

  async function pollStatus(photoId: string, attempts = 15) {
    for (let i = 0; i < attempts; i += 1) {
      try {
        const resp = await fetch(`${API_BASE}/upload/${photoId}/status`);
        if (!resp.ok) return;
        const data = await resp.json();
        const status = data?.status ?? "unknown";
        setPhotos((prev) => prev.map((p) => (p.photo_id === photoId ? { ...p, status } : p)));
        if (status === "completed" || status === "failed") return;
      } catch {
        // Polling failure should not crash upload flow.
      }
      await sleep(1500);
    }
  }

  async function pickAndUpload() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission required", "Allow photo access to upload photos.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      // Compression is done before upload and URI points to compressed output.
      quality: 0.65,
    });

    if (result.canceled || !result.assets?.length) return;

    setUploading(true);
    for (const asset of result.assets) {
      try {
        const formData = new FormData();
        formData.append("user_id", DEMO_USER_ID);
        formData.append("file", {
          uri: asset.uri,
          name: asset.fileName ?? "photo.jpg",
          type: asset.mimeType ?? "image/jpeg",
        } as any);

        const resp = await fetch(`${API_BASE}/upload/`, {
          method: "POST",
          body: formData,
        });
        if (!resp.ok) throw new Error(await parseApiError(resp));
        const data = await resp.json();

        const next: UploadedPhoto = {
          photo_id: data.photo_id,
          storage_url: data.storage_url,
          status: data.status ?? "processing",
        };
        setPhotos((prev) => [next, ...prev]);
        void pollStatus(next.photo_id);
      } catch (err: any) {
        Alert.alert("Upload failed", err.message);
      }
    }
    setUploading(false);
  }

  function getImageUrl(url: string) {
    if (url.startsWith("http")) return url;
    return `${API_BASE}${url}`;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>FotoFindr</Text>
      <Text style={styles.subtitle}>Your AI-powered camera roll</Text>

      <TouchableOpacity style={styles.uploadBtn} onPress={pickAndUpload} disabled={uploading}>
        {uploading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.uploadBtnText}>+ Upload Photos</Text>
        )}
      </TouchableOpacity>

      {photos.length === 0 ? (
        <Text style={styles.empty}>Upload photos to get started.</Text>
      ) : (
        <FlatList
          data={photos}
          keyExtractor={(item) => item.photo_id}
          numColumns={3}
          renderItem={({ item }) => (
            <View style={styles.thumbWrap}>
              <Image source={{ uri: getImageUrl(item.storage_url) }} style={styles.thumb} />
              {item.status && item.status !== "completed" ? (
                <View style={styles.statusBadge}>
                  <Text style={styles.statusText}>{item.status}</Text>
                </View>
              ) : null}
            </View>
          )}
          contentContainerStyle={styles.grid}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", paddingTop: 60, paddingHorizontal: 16 },
  title: { fontSize: 28, fontWeight: "700", color: "#fff", textAlign: "center" },
  subtitle: { fontSize: 14, color: "#888", textAlign: "center", marginBottom: 20 },
  uploadBtn: {
    backgroundColor: "#6c63ff",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 20,
  },
  uploadBtnText: { color: "#fff", fontSize: 16, fontWeight: "600" },
  empty: { color: "#555", textAlign: "center", marginTop: 60, fontSize: 15 },
  grid: { gap: 2 },
  thumbWrap: { flex: 1 / 3, aspectRatio: 1, margin: 1 },
  thumb: { width: "100%", height: "100%", borderRadius: 4 },
  statusBadge: {
    position: "absolute",
    left: 6,
    bottom: 6,
    borderRadius: 8,
    backgroundColor: "rgba(0, 0, 0, 0.65)",
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  statusText: { color: "#fff", fontSize: 10, fontWeight: "600" },
});
