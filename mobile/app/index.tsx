/**
 * Upload Tab — pick photos from camera roll and send to FotoFindr backend.
 */

import { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  Image,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { API_BASE, DEMO_USER_ID } from "../constants/api";

interface UploadedPhoto {
  uri: string;
  photoId: string;
  status: "uploading" | "processing" | "done" | "error";
}

export default function UploadScreen() {
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);

  const pickAndUpload = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsMultipleSelection: true,
      quality: 0.8,
    });

    if (result.canceled) return;

    for (const asset of result.assets) {
      const draft: UploadedPhoto = {
        uri: asset.uri,
        photoId: "",
        status: "uploading",
      };
      setPhotos((prev) => [draft, ...prev]);

      try {
        const form = new FormData();
        form.append("file", { uri: asset.uri, name: "photo.jpg", type: "image/jpeg" } as any);
        form.append("user_id", DEMO_USER_ID);

        const resp = await fetch(`${API_BASE}/upload/`, {
          method: "POST",
          body: form,
        });

        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();

        setPhotos((prev) =>
          prev.map((p) =>
            p.uri === asset.uri ? { ...p, photoId: data.photo_id, status: "processing" } : p
          )
        );

        // Simulate "done" after a delay (processing happens in background)
        setTimeout(() => {
          setPhotos((prev) =>
            prev.map((p) => (p.uri === asset.uri ? { ...p, status: "done" } : p))
          );
        }, 4000);
      } catch {
        setPhotos((prev) =>
          prev.map((p) => (p.uri === asset.uri ? { ...p, status: "error" } : p))
        );
      }
    }
  };

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.uploadBtn} onPress={pickAndUpload}>
        <Text style={styles.uploadBtnText}>+ Select Photos</Text>
      </TouchableOpacity>

      <FlatList
        data={photos}
        keyExtractor={(item) => item.uri}
        numColumns={3}
        renderItem={({ item }) => (
          <View style={styles.thumb}>
            <Image source={{ uri: item.uri }} style={styles.thumbImg} />
            <View style={styles.thumbBadge}>
              {item.status === "uploading" && <ActivityIndicator size="small" color="#fff" />}
              {item.status === "processing" && <Text style={styles.badgeText}>AI</Text>}
              {item.status === "done" && <Text style={styles.badgeText}>✓</Text>}
              {item.status === "error" && <Text style={[styles.badgeText, { color: "#f44" }]}>!</Text>}
            </View>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f0f0f", padding: 8 },
  uploadBtn: {
    backgroundColor: "#6C63FF",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginBottom: 12,
  },
  uploadBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  thumb: { flex: 1 / 3, margin: 2, aspectRatio: 1, position: "relative" },
  thumbImg: { width: "100%", height: "100%", borderRadius: 6 },
  thumbBadge: {
    position: "absolute",
    bottom: 4,
    right: 4,
    backgroundColor: "rgba(0,0,0,0.6)",
    borderRadius: 8,
    padding: 2,
    minWidth: 20,
    alignItems: "center",
  },
  badgeText: { color: "#fff", fontSize: 10, fontWeight: "700" },
});
