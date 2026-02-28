/**
 * Cleanup Tab — review low-value photos (screenshots, blurry, duplicates).
 */

import { useState, useEffect } from "react";
import {
  View,
  Text,
  FlatList,
  Image,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { API_BASE, DEMO_USER_ID } from "../constants/api";

interface CleanupPhoto {
  id: string;
  storage_url: string;
  low_value_flags: string[];
  importance_score: number;
  selected: boolean;
}

export default function CleanupScreen() {
  const [photos, setPhotos] = useState<CleanupPhoto[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/search/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: "unimportant screenshots blurry duplicates",
        user_id: DEMO_USER_ID,
        limit: 50,
      }),
    })
      .then((r) => r.json())
      .then((data) => {
        const lowValue = (data.photos ?? [])
          .filter((p: any) => p.importance_score < 0.4)
          .map((p: any) => ({ ...p, selected: false }));
        setPhotos(lowValue);
      })
      .finally(() => setLoading(false));
  }, []);

  const toggleSelect = (id: string) => {
    setPhotos((prev) => prev.map((p) => (p.id === id ? { ...p, selected: !p.selected } : p)));
  };

  const selectedCount = photos.filter((p) => p.selected).length;

  if (loading) return <ActivityIndicator color="#6C63FF" style={{ flex: 1 }} />;

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>
        {photos.length} low-value photos detected
      </Text>
      {photos.length > 0 && (
        <Text style={styles.sub}>Tap to select photos to delete.</Text>
      )}

      {selectedCount > 0 && (
        <TouchableOpacity
          style={styles.deleteBtn}
          onPress={() => setPhotos((prev) => prev.filter((p) => !p.selected))}
        >
          <Text style={styles.deleteBtnText}>Delete {selectedCount} selected</Text>
        </TouchableOpacity>
      )}

      <FlatList
        data={photos}
        keyExtractor={(item) => item.id}
        numColumns={3}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={[styles.thumb, item.selected && styles.thumbSelected]}
            onPress={() => toggleSelect(item.id)}
          >
            <Image source={{ uri: item.storage_url }} style={styles.thumbImg} />
            <View style={styles.flagRow}>
              {item.low_value_flags.slice(0, 2).map((f) => (
                <View key={f} style={styles.flag}>
                  <Text style={styles.flagText}>{f}</Text>
                </View>
              ))}
            </View>
            {item.selected && (
              <View style={styles.checkOverlay}>
                <Text style={styles.checkMark}>✓</Text>
              </View>
            )}
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <Text style={styles.emptyText}>Your camera roll looks clean!</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f0f0f", padding: 8 },
  heading: { color: "#fff", fontSize: 16, fontWeight: "700", marginBottom: 4, paddingHorizontal: 4 },
  sub: { color: "#666", fontSize: 12, marginBottom: 8, paddingHorizontal: 4 },
  deleteBtn: { backgroundColor: "#c0392b", borderRadius: 10, padding: 12, alignItems: "center", margin: 4, marginBottom: 8 },
  deleteBtnText: { color: "#fff", fontWeight: "700" },
  thumb: { flex: 1 / 3, margin: 2, aspectRatio: 1, position: "relative", borderRadius: 6, overflow: "hidden" },
  thumbSelected: { opacity: 0.6, borderWidth: 2, borderColor: "#6C63FF" },
  thumbImg: { width: "100%", height: "100%" },
  flagRow: { position: "absolute", bottom: 2, left: 2, flexDirection: "row", gap: 2 },
  flag: { backgroundColor: "rgba(0,0,0,0.7)", borderRadius: 4, paddingHorizontal: 4, paddingVertical: 1 },
  flagText: { color: "#f90", fontSize: 8, fontWeight: "700" },
  checkOverlay: { ...StyleSheet.absoluteFillObject, justifyContent: "center", alignItems: "center", backgroundColor: "rgba(108,99,255,0.3)" },
  checkMark: { color: "#fff", fontSize: 28, fontWeight: "900" },
  emptyText: { color: "#555", textAlign: "center", marginTop: 60, fontSize: 16 },
});
