import React, { useState, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Pressable,
} from "react-native";
import { Image } from "expo-image";
import * as MediaLibrary from "expo-media-library";
import { API_BASE, DEMO_USER_ID } from "@/constants/api";
import SearchBar from "@/components/ui/searchbar";

const INDEX_LIMIT = 30; // index the N most recent photos on startup

type LocalPhoto = {
  id: string;
  uri: string;
};

export default function CameraRollScreen() {
  const [photos, setPhotos] = useState<LocalPhoto[]>([]);
  const [loading, setLoading] = useState(true);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [indexDone, setIndexDone] = useState(0);
  const [indexTotal, setIndexTotal] = useState(0);

  useEffect(() => {
    loadAndIndex();
  }, []);

  async function loadAndIndex() {
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

    // Auto-index the most recent photos in the background (no user action needed)
    const toIndex = assets.slice(0, INDEX_LIMIT);
    setIndexTotal(toIndex.length);

    for (let i = 0; i < toIndex.length; i += 3) {
      const batch = toIndex.slice(i, i + 3);
      await Promise.all(batch.map(uploadAsset));
      setIndexDone((prev) => Math.min(prev + batch.length, toIndex.length));
    }
  }

  async function loadMore() {
    const { assets } = await MediaLibrary.getAssetsAsync({
      mediaType: "photo",
      first: indexTotal + 100,
      sortBy: MediaLibrary.SortBy.creationTime,
    });

    setPhotos(assets.map((a) => ({ id: a.id, uri: a.uri })));

    // Auto-index the next batch of photos
    const toIndex = assets.slice(indexTotal, indexTotal + INDEX_LIMIT);
    const prev = indexTotal;
    setIndexTotal((prev) => prev + toIndex.length);

    for (let i = prev; i < prev + INDEX_LIMIT; i += 3) {
      const batch = toIndex.slice(i, i + 3);
      await Promise.all(batch.map(uploadAsset));
      setIndexDone((prev) => prev + batch.length);
    }
  }

  async function uploadAsset(asset: MediaLibrary.Asset) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      // getAssetInfoAsync resolves ph:// → file:// on iOS; fall back to asset.uri
      let uri = asset.uri;
      try {
        const info = await Promise.race([
          MediaLibrary.getAssetInfoAsync(asset),
          new Promise<never>((_, rej) => setTimeout(() => rej(new Error("timeout")), 3000)),
        ]);
        uri = info.localUri ?? asset.uri;
      } catch {
        // use asset.uri as-is
      }

      const formData = new FormData();
      formData.append("user_id", DEMO_USER_ID);
      formData.append("device_uri", asset.uri);  // on-device reference stored in Snowflake
      formData.append("file", { uri, name: asset.filename || "photo.jpg", type: "image/jpeg" } as any);

      await fetch(`${API_BASE}/upload/`, { method: "POST", body: formData, signal: controller.signal });
    } catch {
      // backend offline or timed out — progress still advances
    } finally {
      clearTimeout(timeout);
    }
  }

  const indexing = indexTotal > 0 && indexDone < indexTotal;
  const indexReady = indexTotal > 0 && indexDone >= indexTotal;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>FotoFindr</Text>
      <SearchBar />
      {indexing && (
        <View style={styles.statusBar}>
          <ActivityIndicator size="small" color="#6c63ff" />
          <Text style={styles.statusText}>
            Indexing for search… {indexDone}/{indexTotal}
          </Text>
        </View>
      )}
      {indexReady && (
        <Text style={styles.statusReady}>Ready to search</Text>
      )}

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
          ListFooterComponent={photos.length > 0 ? (
            <Pressable onPress={loadMore}>
              <Text style={styles.loadMoreButton}>
                Load More
              </Text>
            </Pressable>
          ) : null}
          ListFooterComponentStyle={{ paddingBottom: 30 }}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0a0a0a", paddingTop: 60, paddingHorizontal: 16 },
  title: { fontSize: 28, fontWeight: "700", color: "#fff", textAlign: "center", marginBottom: 8 },
  statusBar: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 12 },
  statusText: { color: "#6c63ff", fontSize: 13 },
  statusReady: { color: "#4caf50", fontSize: 13, textAlign: "center", marginBottom: 12 },
  empty: { color: "#aaa", textAlign: "center", marginTop: 60, fontSize: 15 },
  grid: { gap: 2 },
  thumb: { flex: 1 / 3, aspectRatio: 1, margin: 1, borderRadius: 4 },
  loadMoreButton: { color: "#6c63ff", textAlign: "center", marginTop: 16, fontSize: 14, fontWeight: "600" },
});
