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
};

export default function UploadScreen() {
  const [photos, setPhotos] = useState<UploadedPhoto[]>([]);
  const [uploading, setUploading] = useState(false);

  async function pickAndUpload() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission required", "Allow photo access to upload photos.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      quality: 0.8,
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
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        setPhotos((prev) => [{ photo_id: data.photo_id, storage_url: data.storage_url }, ...prev]);
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
            <Image source={{ uri: getImageUrl(item.storage_url) }} style={styles.thumb} />
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
  thumb: { flex: 1 / 3, aspectRatio: 1, margin: 1, borderRadius: 4 },
});
