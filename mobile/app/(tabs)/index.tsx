import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Image } from "expo-image";
import * as MediaLibrary from "expo-media-library";
import * as ImagePicker from "expo-image-picker";
import { API_BASE, DEMO_USER_ID } from "@/constants/api";

type LocalPhoto = {
  id: string;
  uri: string;
};

export default function CameraRollScreen() {
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadCameraRoll();
  }, []);

  async function loadCameraRoll() {
    const { status } = await MediaLibrary.requestPermissionsAsync();
    if (status !== "granted") {
      setPermissionDenied(true);
      setLoading(false);
      return;
    }

    const { assets } = await MediaLibrary.getAssetsAsync({
      mediaType: "photo",
      first: 100,
      sortBy: MediaLibrary.SortBy.creationTime,
    });

    setPhotos(assets.map((a) => ({ id: a.id, uri: a.uri })));
    setLoading(false);
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
      } catch (err: any) {
        Alert.alert("Upload failed", err.message);
      }
    }
    setUploading(false);
    Alert.alert("Done", "Photos sent to AI for indexing.");
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>FotoFindr</Text>
      <Text style={styles.subtitle}>Your AI-powered camera roll</Text>

      <TouchableOpacity style={styles.uploadBtn} onPress={pickAndUpload} disabled={uploading}>
        {uploading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.uploadBtnText}>Send to AI for Search</Text>
        )}
      </TouchableOpacity>

      {loading ? (
        <ActivityIndicator color="#6c63ff" style={{ marginTop: 40 }} />
      ) : permissionDenied ? (
        <Text style={styles.empty}>
          No photo access. Enable it in Settings → FotoFindr → Photos.
        </Text>
      ) : photos.length === 0 ? (
        <Text style={styles.empty}>No photos found on this device.</Text>
      ) : (
        <FlatList
          data={photos}
          keyExtractor={(item) => item.id}
          numColumns={3}
          renderItem={({ item }) => (
            <Image source={{ uri: item.uri }} style={styles.thumb} />
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
  empty: { color: "#aaa", textAlign: "center", marginTop: 60, fontSize: 15 },
  grid: { gap: 2 },
  thumb: { flex: 1 / 3, aspectRatio: 1, margin: 1, borderRadius: 4 },
});
