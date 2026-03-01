import React, { useState, useCallback } from "react";
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
import { useFocusEffect } from "expo-router";
import * as MediaLibrary from "expo-media-library";
import { API_BASE, DEMO_USER_ID } from "@/constants/api";

type UntaggedPhoto = {
  id: string;
  storage_url: string;
  device_uri?: string;
};

export default function CleanupScreen() {
  const [photos, setPhotos] = useState<UntaggedPhoto[]>([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchUntagged = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/untagged/${DEMO_USER_ID}`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setPhotos(data.photos ?? []);
    } catch (err: any) {
      Alert.alert("Error", err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchUntagged();
    }, [fetchUntagged])
  );

  async function handleDelete(photo: UntaggedPhoto) {
    Alert.alert(
      "Delete photo?",
      "This will remove the photo from your device.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => deletePhoto(photo),
        },
      ]
    );
  }

  async function deletePhoto(photo: UntaggedPhoto) {
    setDeleting(photo.id);
    try {
      // Extract asset ID from device_uri (e.g. "ph://ASSET_ID" on iOS)
      const deviceUri = photo.device_uri ?? "";
      const assetId = deviceUri.startsWith("ph://")
        ? deviceUri.slice(5)
        : deviceUri;

      if (assetId) {
        const { status } = await MediaLibrary.requestPermissionsAsync();
        if (status === "granted") {
          await MediaLibrary.deleteAssetsAsync([assetId]);
        }
      }

      // Remove from local state regardless
      setPhotos((prev) => prev.filter((p) => p.id !== photo.id));
    } catch (e: any) {
      Alert.alert("Delete failed", e.message ?? "Could not delete photo.");
    } finally {
      setDeleting(null);
    }
  }

  function imageUrl(storage_url: string) {
    if (storage_url.startsWith("http")) return storage_url;
    return `${API_BASE}${storage_url}`;
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Untagged Photos</Text>
      <Text style={styles.subtitle}>
        {photos.length} photo{photos.length !== 1 ? "s" : ""} with no detected content
      </Text>

      {loading && <ActivityIndicator color="#6c63ff" style={{ marginTop: 30 }} />}

      {!loading && photos.length === 0 && (
        <Text style={styles.empty}>
          No untagged photos.{"\n"}All processed photos have detected content.
        </Text>
      )}

      <FlatList
        data={photos}
        keyExtractor={(item) => item.id}
        numColumns={2}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <Image
              source={{ uri: imageUrl(item.storage_url) }}
              style={styles.thumb}
              contentFit="cover"
            />
            <TouchableOpacity
              style={[styles.deleteBtn, deleting === item.id && styles.deleteBtnDisabled]}
              onPress={() => handleDelete(item)}
              disabled={deleting === item.id}
            >
              <Text style={styles.deleteBtnText}>
                {deleting === item.id ? "Deleting…" : "Delete"}
              </Text>
            </TouchableOpacity>
          </View>
        )}
        contentContainerStyle={{ paddingBottom: 40 }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", paddingTop: 60, paddingHorizontal: 12 },
  title: { fontSize: 24, fontWeight: "700", color: "#fff", marginBottom: 4 },
  subtitle: { fontSize: 13, color: "#666", marginBottom: 20 },
  empty: { color: "#555", textAlign: "center", marginTop: 60, fontSize: 15, lineHeight: 22 },
  card: {
    flex: 1,
    backgroundColor: "#1a1a1a",
    margin: 5,
    borderRadius: 10,
    overflow: "hidden",
  },
  thumb: { width: "100%", aspectRatio: 1, backgroundColor: "#222" },
  deleteBtn: {
    backgroundColor: "#3a0a0a",
    paddingVertical: 10,
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: "#2a0a0a",
  },
  deleteBtnDisabled: { opacity: 0.4 },
  deleteBtnText: { color: "#e05", fontWeight: "600", fontSize: 13 },
});
